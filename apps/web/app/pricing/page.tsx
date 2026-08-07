import Link from "next/link";

const plans = [
  { name: "Free", price: "$0", description: "Build your career profile and run a focused job search.", features: ["20 AI runs/month", "3 resume variants", "5 saved searches", "Job alerts", "5 interview practices"] },
  { name: "Pro", price: "$29/mo", description: "For active candidates using ApplyAI throughout the search.", features: ["500 AI runs/month", "100 resume variants", "100 saved searches", "Job alerts and follow-ups", "100 interview practices", "Full Career Intelligence"] },
  { name: "Team", price: "$99/mo", description: "For career teams and high-volume supported searches.", features: ["2,000 AI runs/month", "500 resume variants", "500 saved searches", "Shared high-volume entitlements", "500 interview practices"] },
];

export default function PricingPage() {
  return <main className="marketing-page"><section className="marketing-hero"><p className="eyebrow">Transparent plans</p><h1>Choose the ApplyAI plan that matches your search.</h1><p>Start free. Upgrade only when your search needs more AI runs, resume variants and interview practice.</p></section><section className="marketing-grid">{plans.map((plan)=><article className="marketing-card" key={plan.name}><p className="eyebrow">{plan.name}</p><h2>{plan.price}</h2><p>{plan.description}</p><ul>{plan.features.map((feature)=><li key={feature}>{feature}</li>)}</ul><Link href="/dashboard" className="ui-button ui-button-primary">Get started</Link></article>)}</section><p className="muted" style={{textAlign:"center",padding:"32px"}}>Checkout is created only for authenticated accounts and only when the configured billing provider is available.</p></main>;
}
