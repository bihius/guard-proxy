"""Background scheduler for tasks like certificate renewal."""

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

from app.database import SessionLocal
from app.models.vhost import VHost
from app.services.certbot_service import CertbotError, CertbotService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def renew_certificates() -> None:
    """Check and renew Let's Encrypt certificates expiring within 30 days."""
    logger.info("Starting certificate renewal check")
    with SessionLocal() as db:
        vhosts = db.query(VHost).filter(VHost.ssl_provider == "letsencrypt").all()
        now = datetime.now(UTC)
        thirty_days = timedelta(days=30)

        for vhost in vhosts:
            # If no expiration date or expiring within 30 days, renew
            if not vhost.ssl_expires_at or (
                vhost.ssl_expires_at.replace(tzinfo=UTC) - now < thirty_days
            ):
                logger.info(f"Renewing certificate for {vhost.domain}")
                certbot = CertbotService()
                try:
                    # In a real background job, we'd find the admin email
                    # or use the generic one.
                    email = f"admin@{vhost.domain}"
                    cert, key = certbot.provision_cert(vhost.domain, email)
                    vhost.ssl_cert = cert
                    vhost.ssl_key = key
                    # Import here to avoid circular imports if needed, or use service
                    from app.services.vhost_service import VHostService
                    vhost.ssl_expires_at = VHostService._parse_cert_expiration(cert)
                    db.commit()
                    logger.info(f"Successfully renewed cert for {vhost.domain}")
                    
                    # Need to trigger config generation to write the new certs to disk
                    # This relies on config apply logic.
                    from app.models.policy import Policy
                    from app.models.rule_override import RuleOverride
                    from app.services.config_apply import apply as apply_config
                    from app.services.config_generator import generate
                    try:
                        policies = db.query(Policy).all()
                        rule_overrides = db.query(RuleOverride).all()
                        generated = generate(
                            db.query(VHost).all(), policies, rule_overrides
                        )
                        apply_config(generated)
                    except Exception as e:
                        logger.error(f"Failed to apply config after cert renewal: {e}")
                except CertbotError as e:
                    logger.error(f"Failed to renew certificate for {vhost.domain}: {e}")

def start_scheduler() -> None:
    """Start the background scheduler."""
    scheduler.add_job(renew_certificates, 'interval', days=1, id='renew_certificates')
    scheduler.start()
    logger.info("Background scheduler started")

def stop_scheduler() -> None:
    """Stop the background scheduler."""
    scheduler.shutdown()
    logger.info("Background scheduler stopped")
