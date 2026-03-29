import { ArrowRightIcon, InfoIcon } from "@/components/icons";

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
          icon={<InfoIcon className="text-accent" />}
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
          icon={<ArrowRightIcon className="text-fg-muted" />}
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
