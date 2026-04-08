import { useState } from 'react'
import { Link } from 'react-router-dom'

const features = [
  { text: 'Full access to Insider Cluster Alerts dashboard', accent: 'green' },
  { text: 'Full access to Insider-Event Intelligence dashboard', accent: 'purple' },
  { text: 'Decision cards with BUY / WATCH / PASS for cluster signals', accent: 'green' },
  { text: 'Weekly CSV/data file delivery (S3 or SFTP)', accent: 'gray' },
  { text: 'Full anomaly dataset export (178+ validated cases)', accent: 'gray' },
  { text: 'Insider cluster signals with conviction scoring', accent: 'green' },
  { text: 'Signal metadata: insider names, titles, transaction amounts, timing', accent: 'gray' },
  { text: 'Company profiles with insider activity history', accent: 'gray' },
  { text: 'Live performance tracker vs market benchmark', accent: 'gray' },
  { text: 'Coverage: 3,600+ US public companies', accent: 'gray' },
  { text: 'Update frequency: Daily scans', accent: 'gray' },
]

const faqs = [
  {
    q: 'What data sources do you use?',
    a: 'All data is sourced from SEC EDGAR Form 4 and 8-K filings. Every data point is publicly verifiable.',
  },
  {
    q: 'How often is data updated?',
    a: 'We scan SEC EDGAR daily. Near real-time scanning (10-minute intervals) is on our roadmap.',
  },
  {
    q: 'Do you offer a trial?',
    a: 'We offer a 2-week evaluation period for qualified institutional buyers. Contact us to discuss.',
  },
  {
    q: "What's included in the data file?",
    a: 'CSV with ticker, company name, event type, insider names and titles, transaction amounts, timing relative to SEC filings, and conviction scoring.',
  },
  {
    q: 'Can I integrate this into my existing models?',
    a: 'Yes. Our data files are designed for easy integration into quantitative models. API access for programmatic integration available on request.',
  },
]

function CheckIcon({ color }: { color: string }) {
  const colorClass =
    color === 'green'
      ? 'text-green-500'
      : color === 'purple'
        ? 'text-purple-500'
        : 'text-gray-400'
  return (
    <svg
      className={`w-5 h-5 ${colorClass} flex-shrink-0 mt-0.5`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

export default function Pricing() {
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  return (
    <div className="max-w-5xl mx-auto">
      {/* Hero */}
      <section className="text-center pt-14 pb-10">
        <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight mb-3">
          Institutional Access
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Two Products. One Edge. Full access to actionable insider signals and deep event intelligence.
        </p>
      </section>

      {/* Pricing Card */}
      <section className="mb-6 flex justify-center">
        <div className="w-full max-w-xl bg-white rounded-xl border border-gray-200 shadow-sm p-8">
          <div className="text-center mb-8">
            <div className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Annual Subscription
            </div>
            <div className="flex items-baseline justify-center gap-1">
              <span className="text-5xl font-extrabold text-gray-900">$24,000</span>
              <span className="text-gray-500 text-lg">/year</span>
            </div>
          </div>

          <ul className="space-y-3 mb-8">
            {features.map((f, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-gray-700">
                <CheckIcon color={f.accent} />
                <span>{f.text}</span>
              </li>
            ))}
          </ul>

          <a
            href="mailto:hello@lookinsight.ai?subject=LookInsight%20AI%20%E2%80%94%20Institutional%20Access"
            className="block w-full text-center py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-semibold text-sm transition-colors"
          >
            Get Started
          </a>
        </div>
      </section>

      {/* Flexible terms note */}
      <p className="text-center text-sm text-gray-400 mb-16">
        Flexible terms for early partners. Custom delivery formats and API access available on request.
      </p>

      {/* Two Products Section */}
      <section className="mb-16">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-2">
          Two Products. One Edge.
        </h2>
        <p className="text-center text-sm text-gray-500 mb-8">
          Both included in your subscription.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Insider Cluster Alerts */}
          <div className="bg-white rounded-xl border-2 border-green-200 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-2.5 h-2.5 rounded-full bg-green-500"></span>
              <h3 className="font-bold text-gray-900">Insider Cluster Alerts</h3>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">
              Actionable trade signals when multiple insiders buy shares in a coordinated window.
              75% hit rate on quality signals (mid-cap + $100K+ value, 84 signals validated).
            </p>
          </div>

          {/* Insider-Event Intelligence */}
          <div className="bg-white rounded-xl border-2 border-purple-200 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
              <h3 className="font-bold text-gray-900">Insider-Event Intelligence</h3>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">
              Deep intelligence on who traded before material SEC filings.
              Median 15-day insider lead time.
            </p>
          </div>
        </div>
      </section>

      {/* Accuracy proof strip */}
      <section className="mb-16">
        <Link
          to="/accuracy"
          className="block bg-gray-50 border border-gray-200 rounded-xl p-6 hover:bg-gray-100 transition-colors"
        >
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide text-center mb-3">
            Verified Track Record
          </p>
          <div className="flex items-center justify-center gap-8 flex-wrap">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">67.8%</div>
              <div className="text-xs text-gray-500">Cluster Hit Rate</div>
            </div>
            <div className="h-8 w-px bg-gray-300 hidden sm:block"></div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">15 days</div>
              <div className="text-xs text-gray-500">Median Insider Lead Time</div>
            </div>
            <div className="h-8 w-px bg-gray-300 hidden sm:block"></div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">3,600+</div>
              <div className="text-xs text-gray-500">Companies Covered</div>
            </div>
            <div className="h-8 w-px bg-gray-300 hidden sm:block"></div>
            <div className="text-center">
              <span className="text-sm font-semibold text-primary-600 underline">
                View Live Accuracy &rarr;
              </span>
            </div>
          </div>
        </Link>
      </section>

      {/* FAQ */}
      <section className="mb-16">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-6">
          Frequently Asked Questions
        </h2>
        <div className="max-w-2xl mx-auto space-y-3">
          {faqs.map((faq, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <button
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
                className="w-full flex items-center justify-between px-6 py-4 text-left"
              >
                <span className="font-semibold text-sm text-gray-900">{faq.q}</span>
                <svg
                  className={`w-5 h-5 text-gray-400 flex-shrink-0 transition-transform ${
                    openFaq === i ? 'rotate-180' : ''
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {openFaq === i && (
                <div className="px-6 pb-4">
                  <p className="text-sm text-gray-600 leading-relaxed">{faq.a}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="text-center py-12 mb-8 border-t border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Ready to see the edge?</h2>
        <p className="text-gray-600 mb-6">
          Contact us to schedule a walkthrough or start your evaluation.
        </p>
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <a
            href="mailto:hello@lookinsight.ai?subject=LookInsight%20AI%20%E2%80%94%20Institutional%20Access"
            className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium text-sm"
          >
            Get Started
          </a>
          <Link
            to="/"
            className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium text-sm"
          >
            Explore Dashboard
          </Link>
        </div>
      </section>
    </div>
  )
}
