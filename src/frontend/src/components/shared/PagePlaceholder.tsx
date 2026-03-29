import { EmptyState } from "./EmptyState";
import { PageHeader } from "./PageHeader";
import { SectionCard } from "./SectionCard";
import { StatusBadge } from "./StatusBadge";

type PagePlaceholderProps = {
  title: string;
  description: string;
  eyebrow: string;
};

export function PagePlaceholder({
  title,
  description,
  eyebrow,
}: PagePlaceholderProps) {
  return (
    <section className="space-y-8">
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        description={description}
        actions={<StatusBadge label="Bootstrap" tone="info" />}
      />

      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <SectionCard
          title="Why it exists"
          description="Shared placeholder so every route lives inside the same application shell."
          icon={<InfoIcon />}
        >
          <p className="text-sm leading-6 text-fg-muted">
            Replace only the page content without rebuilding layout, navigation,
            or chrome. This helps the team work in parallel without fragmenting
            the app structure.
          </p>
        </SectionCard>

        <SectionCard
          title="Next step"
          description="This is the handoff point for the real feature implementation."
          icon={<ArrowIcon />}
        >
          <EmptyState
            title="Feature UI has not been started yet"
            description="Replace this area with the real screen when the assigned task begins. Until then, this placeholder keeps routing, layout, and shared component usage consistent."
          />
        </SectionCard>
      </div>
    </section>
  );
}

function InfoIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-accent"
    >
      <circle cx="8" cy="8" r="6.5" />
      <line x1="8" y1="7" x2="8" y2="11" />
      <circle cx="8" cy="5" r="0.5" fill="currentColor" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-fg-muted"
    >
      <line x1="3" y1="8" x2="13" y2="8" />
      <polyline points="9 4 13 8 9 12" />
    </svg>
  );
}
