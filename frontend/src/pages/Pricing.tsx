import { Link } from 'react-router-dom'

const tiers = [
  {
    name: 'Analyst',
    price: '$499',
    target: 'Small funds, independent analysts, family offices',
    highlight: false,
    features: [
      'Signal feed (HIGH & MEDIUM, 24h delay)',
      '30-second Decision Cards (BUY / WATCH / PASS)',
      'Company profiles with officers & insider summary',
      'Stock price charts with filing markers',
      '50 signal lookups per month',
      'Web dashboard access',
    ],
    cta: 'Start 14-Day Trial',
  },
  {
    name: 'Professional',
    price: '$1,499',
    target: 'Mid-size hedge funds, event-driven funds',
    highlight: true,
    badge: 'Most Popular',
    features: [
      'Everything in Analyst, plus:',
      'Real-time signals (no delay)',
      'Insider cluster alerts — the leading indicator',
      'Full LLM analysis with source citations',
      'Company intelligence reports',
      'API access with key (500 calls/mo)',
      'Export to CSV / JSON',
      'Email & webhook alerts for HIGH signals',
    ],
    cta: 'Start 14-Day Trial',
  },
  {
    name: 'Institutional',
    price: '$4,999',
    target: 'Large funds, prime brokers, compliance desks',
    highlight: false,
    features: [
      'Everything in Professional, plus:',
      'Unlimited API access',
      'Compliance suite (OFAC, PEP screening, risk scoring)',
      'Network graph analysis (board interlocks, address clustering)',
      'Full market scan — entire SEC universe',
      'Custom signal rules & watchlists',
      'Bulk data export',
      'Dedicated support & SLA guarantee',
    ],
    cta: 'Request Demo',
  },
]

const comparisons = [
  { feature: 'Signal feed', analyst: '24h delay', pro: 'Real-time', inst: 'Real-time' },
  { feature: 'Insider cluster alerts', analyst: 'View only', pro: 'Alerts', inst: 'Alerts' },
  { feature: 'Decision cards', analyst: true, pro: true, inst: true },
  { feature: 'LLM analysis', analyst: 'Summary', pro: 'Full + citations', inst: 'Full + citations' },
  { feature: 'API access', analyst: false, pro: '500 calls/mo', inst: 'Unlimited' },
  { feature: 'Compliance / OFAC', analyst: false, pro: false, inst: true },
  { feature: 'Graph analysis', analyst: false, pro: false, inst: true },
  { feature: 'Email / webhook alerts', analyst: false, pro: true, inst: true },
  { feature: 'Market scan', analyst: false, pro: false, inst: true },
  { feature: 'Export (CSV / JSON)', analyst: false, pro: true, inst: true },
]

function Check() {
  return (
    <svg className="w-5 h-5 text-green-500 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function Cross() {
  return (
    <svg className="w-5 h-5 text-gray-300 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function CellValue({ value }: { value: boolean | string }) {
  if (value === true) return <Check />
  if (value === false) return <Cross />
  return <span className="text-sm text-gray-700">{value}</span>
}

export default function Pricing() {
  return (
    <div className="max-w-6xl mx-auto">

      {/* Hero */}
      <section className="text-center py-14 mb-4">
        <h1 className="text-4xl font-extrabold text-gray-900 mb-3 tracking-tight">
          Intelligence That <span className="text-primary-600">Pays for Itself</span>
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto mb-2">
          We detected the Splunk&ndash;Cisco acquisition 6 months early. How much is a 6-month head start worth to your fund?
        </p>
        <p className="text-sm text-gray-400">
          14-day free trial on all plans. No credit card required.
        </p>
      </section>

      {/* Tier Cards */}
      <section className="mb-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative rounded-xl border p-7 flex flex-col ${
                tier.highlight
                  ? 'border-primary-500 bg-white shadow-lg ring-2 ring-primary-500/20'
                  : 'border-gray-200 bg-white shadow-sm'
              }`}
            >
              {tier.badge && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-primary-600 text-white text-xs font-bold rounded-full uppercase tracking-wide">
                  {tier.badge}
                </span>
              )}

              <div className="mb-5">
                <h3 className="text-lg font-bold text-gray-900">{tier.name}</h3>
                <p className="text-sm text-gray-500 mt-1">{tier.target}</p>
              </div>

              <div className="mb-6">
                <span className="text-4xl font-extrabold text-gray-900">{tier.price}</span>
                <span className="text-gray-500 ml-1">/mo</span>
              </div>

              <ul className="space-y-3 mb-8 flex-1">
                {tier.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-gray-700">
                    {f.startsWith('Everything') ? (
                      <span className="text-primary-600 font-medium">{f}</span>
                    ) : (
                      <>
                        <svg className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        {f}
                      </>
                    )}
                  </li>
                ))}
              </ul>

              <a
                href="mailto:shreshta@lookinsight.ai?subject=Corporate Intelligence — Interested in the plan"
                className={`block text-center py-2.5 rounded-lg font-medium text-sm transition-colors ${
                  tier.highlight
                    ? 'bg-primary-600 text-white hover:bg-primary-700'
                    : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                }`}
              >
                {tier.cta}
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* Feature Comparison Table */}
      <section className="mb-16">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-6">
          Feature Comparison
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-6 py-3 text-sm font-semibold text-gray-600 w-1/4">Feature</th>
                <th className="text-center px-6 py-3 text-sm font-semibold text-gray-600">Analyst</th>
                <th className="text-center px-6 py-3 text-sm font-semibold text-primary-600">Professional</th>
                <th className="text-center px-6 py-3 text-sm font-semibold text-gray-600">Institutional</th>
              </tr>
            </thead>
            <tbody>
              {comparisons.map((row, i) => (
                <tr key={row.feature} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="px-6 py-3 text-sm font-medium text-gray-900">{row.feature}</td>
                  <td className="px-6 py-3 text-center"><CellValue value={row.analyst} /></td>
                  <td className="px-6 py-3 text-center"><CellValue value={row.pro} /></td>
                  <td className="px-6 py-3 text-center"><CellValue value={row.inst} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Why Institutional Clients Trust Us */}
      <section className="mb-16">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-6">
          Why Funds Choose Us
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">Evidence-Based, Not Opinion</h3>
            <p className="text-sm text-gray-600">
              Every signal traces back to an SEC filing. Every insider trade links to a Form 4.
              We surface patterns — you make the call.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">Leading Indicators, Not Headlines</h3>
            <p className="text-sm text-gray-600">
              Insider cluster buying detected weeks before announcements. Material Agreement filings
              flagged months before deal closings. Time advantage is alpha.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">30-Second Decisions</h3>
            <p className="text-sm text-gray-600">
              Each signal produces a BUY / WATCH / PASS verdict with conviction score, price movement,
              and insider direction. Designed for how analysts actually work.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">Hidden Network Connections</h3>
            <p className="text-sm text-gray-600">
              Board interlocks, shared officers, and address clustering reveal connections
              between deal parties invisible in flat data.
            </p>
          </div>
        </div>
      </section>

      {/* Case Study Proof Point */}
      <section className="mb-16">
        <div className="bg-gradient-to-r from-gray-900 to-primary-900 rounded-xl p-8 text-white">
          <div className="flex items-center gap-2 mb-3">
            <span className="px-2.5 py-1 bg-purple-600 rounded text-xs font-bold uppercase">Proven Track Record</span>
          </div>
          <h3 className="text-xl font-bold mb-2">Splunk Acquisition — Detected 6 Months Early</h3>
          <p className="text-gray-300 leading-relaxed mb-4">
            September 2023: Splunk files an 8-K with Item 1.01 (Material Agreement) + Item 5.03
            (Governance Changes). Our system flags it <span className="text-red-400 font-semibold">HIGH</span>.
            March 2024: Cisco completes the $28B acquisition. Subscribers who acted on the signal
            had a 6-month window before the market priced it in.
          </p>
          <div className="flex items-center gap-6 text-sm mb-4">
            <div>
              <span className="text-gray-400">Signal Filed:</span>{' '}
              <span className="font-medium">Sep 21, 2023</span>
            </div>
            <div>
              <span className="text-gray-400">Deal Closed:</span>{' '}
              <span className="font-medium">Mar 18, 2024</span>
            </div>
            <div>
              <span className="text-gray-400">Lead Time:</span>{' '}
              <span className="font-semibold text-green-400">~6 months</span>
            </div>
          </div>
          <Link
            to="/signal/0001104659-23-102594"
            className="inline-block px-4 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-sm font-medium transition-colors"
          >
            See the live signal story &rarr;
          </Link>
        </div>
      </section>

      {/* FAQ */}
      <section className="mb-16">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-6">
          Frequently Asked Questions
        </h2>
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">How does the 14-day trial work?</h3>
            <p className="text-sm text-gray-600">
              Sign up with your work email and get full Professional-tier access for 14 days.
              No credit card required. See insider cluster alerts, real-time signals, and full LLM analysis
              before you commit.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">What data sources do you use?</h3>
            <p className="text-sm text-gray-600">
              All signals are derived from public SEC filings: 8-K filings (EDGAR), Form 4 insider
              trading reports, and DEF 14A proxy statements. We process them with LLMs to extract
              structured intelligence and cross-reference patterns.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">Can I integrate with my existing tools?</h3>
            <p className="text-sm text-gray-600">
              Professional and Institutional tiers include API access. Pull signals into your
              trading platform, compliance system, or custom dashboards via our REST API.
              Webhook alerts push new HIGH signals to Slack, email, or any endpoint.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">Do you offer annual billing?</h3>
            <p className="text-sm text-gray-600">
              Yes. Annual plans save 20% compared to monthly. Contact us for custom enterprise
              agreements and multi-seat pricing.
            </p>
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="text-center py-12 mb-8 border-t border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Ready to see the signals?</h2>
        <p className="text-gray-600 mb-6">
          Start your 14-day trial or book a demo with our team.
        </p>
        <div className="flex items-center justify-center gap-4">
          <a
            href="mailto:shreshta@lookinsight.ai?subject=Corporate Intelligence — Start Trial"
            className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium"
          >
            Start Free Trial
          </a>
          <a
            href="mailto:shreshta@lookinsight.ai?subject=Corporate Intelligence — Request Demo"
            className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            Request Demo
          </a>
          <Link
            to="/"
            className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            Explore Dashboard
          </Link>
        </div>
      </section>
    </div>
  )
}
