import { useParams } from "react-router-dom";

import { PagePlaceholder } from "@/components/shared/PagePlaceholder";

export function VHostDetailPage() {
  const { vhostId } = useParams();

  return (
    <PagePlaceholder
      eyebrow="VHosts"
      title={`VHost detail placeholder${vhostId ? ` #${vhostId}` : ""}`}
      description="This route proves we already support a dedicated detail view. Later it can become a read-only page or a drawer entry point for the assigned team task."
    />
  );
}
