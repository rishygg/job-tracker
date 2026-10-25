import { BookOpen, Compass, FileSearch, GraduationCap, Lightbulb, MessagesSquare, Route, Target } from "lucide-react";
import { PageHeader } from "../components/ui";

function Upcoming({ items }: { items: { icon: typeof Compass; title: string; text: string; stage: string }[] }) {
  return (
    <div className="grid md:grid-cols-2 gap-4">
      {items.map((i) => (
        <div key={i.title} className="card p-5 flex gap-4">
          <div className="w-10 h-10 rounded-lg bg-canvas border border-line flex items-center justify-center text-ink-muted shrink-0"><i.icon size={18} /></div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-[14.5px]">{i.title}</h3>
              <span className="text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">{i.stage}</span>
            </div>
            <p className="text-[13px] text-ink-muted mt-1">{i.text}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export function DiscoverPlaceholder() {
  return (
    <div className="max-w-5xl">
      <PageHeader title="Discover" subtitle="Saved opportunities and job-fit analysis. Coming in the next stages." />
      <Upcoming items={[
        { icon: FileSearch, title: "CV fit analysis", stage: "Stage 2", text: "Paste a job description and get strengths, gaps, evidence from your CV, blockers (language, permit, location) and a recommendation: apply, apply with caveats, or deprioritise. Essential and preferred requirements are kept separate." },
        { icon: Target, title: "Target CV and cover letter", stage: "Stage 2", text: "The strongest version of your CV for a specific job, with every line marked as backed by your experience, partly backed, or a gap, so you can borrow what's true." },
        { icon: Compass, title: "Saved opportunities", stage: "Stage 3", text: "Keep roles you haven't applied to yet, ranked by fit, with deadlines feeding into today's priorities." },
        { icon: Route, title: "Career paths", stage: "Stage 3", text: "Which role families your profile and results point towards, and what it would take to move into adjacent ones." },
      ]} />
    </div>
  );
}

export function CareerPlaceholder() {
  return (
    <div className="max-w-5xl">
      <PageHeader title="Career development" subtitle="Learn from every interview and close the right skill gaps. Coming in stage 3." />
      <Upcoming items={[
        { icon: MessagesSquare, title: "Interview learning journal", stage: "Stage 3", text: "After each interview, record the questions, skills assessed, what you struggled with, feedback and next steps. Recurring themes are surfaced over time." },
        { icon: GraduationCap, title: "Personalised interview practice", stage: "Stage 3", text: "Practice questions generated from your own interview history, not generic lists, focused on the areas you've found hardest." },
        { icon: BookOpen, title: "Story bank", stage: "Stage 3", text: "Reusable examples (STAR stories) linked to the skills they demonstrate and the interviews where you used them." },
        { icon: Lightbulb, title: "Skills report and industry notes", stage: "Stage 3", text: "The skills requested most across the roles you want, emerging gaps, and a place to save what you learn about each industry." },
      ]} />
    </div>
  );
}
