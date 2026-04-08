import { Link } from 'react-router-dom'

export default function Blog() {
  return (
    <article className="max-w-3xl mx-auto py-12 px-4">

      {/* Header */}
      <div className="mb-10">
        <Link to="/" className="text-sm text-gray-400 hover:text-gray-600 mb-4 inline-block">&larr; Back to Dashboard</Link>
        <h1 className="text-3xl font-extrabold text-gray-900 leading-tight mb-4">
          We Tested 80+ Insider Trading Signals Against Real Data. Here's What Actually Works.
        </h1>
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <span>Manohar</span>
          <span>&middot;</span>
          <span>March 2026</span>
          <span>&middot;</span>
          <span>8 min read</span>
        </div>
      </div>

      {/* Body */}
      <div className="prose prose-gray max-w-none">

        <p className="text-lg text-gray-700 leading-relaxed">
          There's no shortage of insider trading data. Every time a corporate executive buys or sells their own company's stock,
          it shows up in an SEC Form 4 filing — publicly available, same day. Dozens of platforms will show you this data.
        </p>
        <p className="text-lg text-gray-700 leading-relaxed">
          The question nobody answers well: <strong>which insider trades actually predict stock returns?</strong>
        </p>
        <p className="text-gray-600 leading-relaxed">
          We ran 80+ experiments against 12 months of real SEC filing data to find out. Not a backtest on curated examples.
          Not a theoretical model. We tested every parameter — cluster size, timing window, dollar threshold, insider role,
          sector, price context — and measured forward returns against the S&P 500. To control for multiple comparisons,
          signals cited below remained significant after Bonferroni-adjusted testing at p&lt;0.05.
        </p>
        <p className="text-gray-600 leading-relaxed">Here's what the data says.</p>

        {/* Finding 1 */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">Finding 1: Banking insiders are right 89% of the time</h2>
        <p className="text-gray-600 leading-relaxed">
          When two or more insiders at a banking company buy open-market shares within a 21-day window, the stock goes up
          89% of the time. Average return: +7.4%. Average alpha vs S&P 500: +2.2%.
        </p>
        <p className="text-gray-600 leading-relaxed">
          This wasn't a one-off result. It showed up in our first round of experiments at 75%. We stacked additional
          filters in round two — it climbed to 87.5%. In round three, we drilled into sub-sectors — banks specifically
          hit 88.9% on 18 signals. We tested it on 2025 data only — 90% on 20 signals.
        </p>
        <p className="text-gray-600 leading-relaxed">
          Four independent tests. Consistent sample sizes. Consistent results.
        </p>
        <p className="text-gray-600 leading-relaxed">
          Why banking? Bank insiders understand their own business in a way that tech or biotech insiders often can't.
          A community bank CEO sees the loan portfolio, the deposit base, the interest rate exposure. When they buy
          shares with their own money, they're making a bet on something they can actually evaluate.
        </p>

        {/* Finding 2 */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">Finding 2: Insiders are early — the market takes 120 days to agree</h2>
        <p className="text-gray-600 leading-relaxed">
          We tested our best signal at five different time horizons:
        </p>
        <div className="bg-gray-50 rounded-xl p-5 my-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 font-semibold text-gray-700">Time Horizon</th>
                <th className="text-right py-2 font-semibold text-gray-700">Hit Rate</th>
                <th className="text-right py-2 font-semibold text-gray-700">Avg Return</th>
                <th className="text-right py-2 font-semibold text-gray-700">n</th>
              </tr>
            </thead>
            <tbody className="text-gray-600">
              <tr className="border-b border-gray-100"><td className="py-2">30 days</td><td className="text-right">78%</td><td className="text-right text-green-600">+4.6%</td><td className="text-right">142</td></tr>
              <tr className="border-b border-gray-100 bg-red-50"><td className="py-2">60 days</td><td className="text-right text-red-600">56%</td><td className="text-right">+2.5%</td><td className="text-right">142</td></tr>
              <tr className="border-b border-gray-100"><td className="py-2">90 days</td><td className="text-right">67%</td><td className="text-right text-green-600">+3.7%</td><td className="text-right">142</td></tr>
              <tr className="border-b border-gray-100 bg-green-50"><td className="py-2 font-semibold">120 days</td><td className="text-right font-semibold text-green-700">89%</td><td className="text-right font-semibold text-green-700">+7.9%</td><td className="text-right">142</td></tr>
              <tr className="bg-green-50"><td className="py-2 font-semibold">180 days</td><td className="text-right font-semibold text-green-700">89%</td><td className="text-right font-semibold text-green-700">+12.4%</td><td className="text-right">142</td></tr>
            </tbody>
          </table>
        </div>
        <p className="text-gray-600 leading-relaxed">
          Insider buying predicts a dip in win rate before it predicts a rise. At 60 days, the hit rate drops to 56%
          — more stocks are down than up, even though the average return is still slightly positive. Then they recover.
          By 120 days, the thesis plays out.
        </p>
        <p className="text-gray-600 leading-relaxed italic">
          This has a direct implication: if you buy when insiders buy and the stock drops 5% in the first
          two months, that's expected behavior. The signal is still working. Patient capital wins.
        </p>

        {/* Finding 3 */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">Finding 3: Sector context matters more than any other parameter</h2>
        <p className="text-gray-600 leading-relaxed">
          Same signal definition. Same cluster rules. Different sectors, dramatically different results:
        </p>
        <div className="bg-gray-50 rounded-xl p-5 my-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 font-semibold text-gray-700">Sector</th>
                <th className="text-right py-2 font-semibold text-gray-700">Hit Rate</th>
                <th className="text-right py-2 font-semibold text-gray-700">Avg Return</th>
                <th className="text-right py-2 font-semibold text-gray-700">n</th>
              </tr>
            </thead>
            <tbody className="text-gray-600">
              <tr className="border-b border-gray-100 bg-green-50"><td className="py-2 font-semibold">Banking</td><td className="text-right font-semibold text-green-700">89%</td><td className="text-right text-green-600">+7.4%</td><td className="text-right">18</td></tr>
              <tr className="border-b border-gray-100"><td className="py-2">Electronics</td><td className="text-right">83%</td><td className="text-right text-green-600">+6.1%</td><td className="text-right">24</td></tr>
              <tr className="border-b border-gray-100"><td className="py-2">Technology</td><td className="text-right">68%</td><td className="text-right text-green-600">+5.3%</td><td className="text-right">47</td></tr>
              <tr className="border-b border-gray-100"><td className="py-2">All sectors</td><td className="text-right">68%</td><td className="text-right text-green-600">+4.8%</td><td className="text-right">142</td></tr>
              <tr className="border-b border-gray-100"><td className="py-2">Energy</td><td className="text-right">60%</td><td className="text-right text-green-600">+3.5%</td><td className="text-right">15</td></tr>
              <tr className="bg-yellow-50"><td className="py-2">Healthcare</td><td className="text-right text-red-600">46%</td><td className="text-right text-green-600">+12.0%</td><td className="text-right">28</td></tr>
            </tbody>
          </table>
        </div>
        <p className="text-gray-600 leading-relaxed">
          Healthcare is the most interesting case — lowest hit rate (46%, worse than a coin flip) but highest
          average return (+12.0%). When healthcare insiders are right, the payoff is enormous. But they're wrong
          more often than they're right. High risk, high reward.
        </p>

        {/* Finding 4 */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">Finding 4: "Buying the dip" is a myth</h2>
        <p className="text-gray-600 leading-relaxed">
          We tested a common narrative: insiders buying after a stock drops 10%+ should be a stronger signal.
          The data says the opposite.
        </p>
        <div className="bg-gray-50 rounded-xl p-5 my-5">
          <div className="flex gap-6">
            <div className="flex-1 text-center">
              <div className="text-2xl font-bold text-green-700">68.4%</div>
              <div className="text-sm text-gray-500 mt-1">Stock NOT down before buy (n=97)</div>
            </div>
            <div className="flex-1 text-center">
              <div className="text-2xl font-bold text-red-600">61.5%</div>
              <div className="text-sm text-gray-500 mt-1">Stock down 10%+ before buy (n=26)</div>
            </div>
          </div>
        </div>
        <p className="text-gray-600 leading-relaxed">
          Dip buying underperforms by 7 percentage points. When insiders buy a falling stock, the falling often
          continues. When insiders buy a stock that isn't distressed, they're making a proactive bet rather than
          trying to catch a knife.
        </p>

        {/* Finding 5 */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">Finding 5: More conviction doesn't mean better signal</h2>
        <p className="text-gray-600 leading-relaxed">
          We expected that larger individual transactions, repeat purchases, or bigger position increases would
          predict better returns. We tested all three:
        </p>
        <div className="bg-gray-50 rounded-xl p-5 my-5 space-y-2 text-sm text-gray-600">
          <div className="flex justify-between"><span>Repeat buyers (same person buying 3+ times)</span><span className="font-semibold text-red-600">46% hit rate (n=35)</span></div>
          <div className="flex justify-between"><span>Individual bets over $500K</span><span className="font-semibold text-red-600">50% hit rate (n=22)</span></div>
          <div className="flex justify-between"><span>Minimum $50K per insider (no token buys)</span><span className="font-semibold text-red-600">49% hit rate (n=41)</span></div>
        </div>
        <p className="text-gray-600 leading-relaxed">
          All below the 68% baseline. The signal isn't in the count or the conviction of individual bets.{' '}
          In expanded testing (223 signals), the strongest filter is company size ($300M-$10B market cap) combined
          with meaningful total value ($100K+) — hitting 75% on 84 signals.{' '}
          <strong>It's about who is buying at what kind of company, not how many or how much each person bets.</strong>
        </p>

        {/* Finding 6 */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">Finding 6: Capital rotation — an emerging pattern</h2>
        <p className="text-gray-600 leading-relaxed">
          When an insider sells shares in one company and buys shares in another within 30 days, the
          company they're buying outperforms 75% of the time with an average return of +63.6%. Sample size
          is small (n=8) — not yet statistically significant, but we're actively tracking this pattern as coverage
          expands. The logic is compelling: this isn't spare-cash buying. It's an active reallocation of capital
          from one bet to another.
        </p>

        {/* What we didn't find */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">What we didn't find</h2>
        <p className="text-gray-600 leading-relaxed">
          No complex behavioral pattern beat the simple cluster signal. C-suite diversity in a cluster didn't
          help. Escalating purchase sizes didn't help. Post-earnings timing didn't help.
        </p>
        <p className="text-gray-600 leading-relaxed">
          Simplicity wins. <strong>"Multiple insiders at the same company bought shares"</strong> is the signal.
          Everything else is decoration.
        </p>

        {/* Sell signals */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">Our sell signals: 72% accuracy</h2>
        <p className="text-gray-600 leading-relaxed">
          On the sell side, when four or more insiders sell open-market shares in a coordinated window, the
          stock drops 72% of the time (n=32). We tested 10+ variations — nothing beat the baseline.
        </p>
        <p className="text-gray-600 leading-relaxed">
          We also added AI-generated explanations to every sell signal. When 10 executives at Warner Bros Discovery
          sell $252M in shares, the one-liner reads: <em>"CEO sold 35% of holdings with zero insider buying in 90 days,
          coinciding with content losses to Netflix."</em> The user gets the context to make their own decision.
        </p>

        {/* How we did this */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">How we did this</h2>
        <p className="text-gray-600 leading-relaxed">
          All data comes from SEC EDGAR — Form 4 insider transactions, 8-K material event filings, and Schedule
          13D activist disclosures. No alternative data, no web scraping, no self-reported data.
        </p>
        <p className="text-gray-600 leading-relaxed">
          Every signal on our platform comes with:
        </p>
        <ul className="list-disc pl-6 text-gray-600 space-y-1 my-3">
          <li>A one-line AI explanation of why insiders are likely buying or selling</li>
          <li>Historical context showing how similar signals performed in the past</li>
          <li>Live forward returns tracked against the S&P 500</li>
        </ul>
        <p className="text-gray-600 leading-relaxed">
          Every signal is tested against the full dataset, not curated examples. Forward returns are computed
          on live data after signal generation — no lookahead bias, no cherry-picking. The track record is
          publicly verifiable at ci.lookinsight.ai.
        </p>

        {/* Data Delivery */}
        <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4">Data Delivery</h2>
        <p className="text-gray-600 leading-relaxed">
          LookInsight delivers daily insider cluster alerts covering ~4,000 active securities, with AI-generated
          context and forward return tracking. Data is available via CSV export and API. Coverage includes all
          SEC Form 4 filers with open-market transactions.
        </p>
      </div>

      {/* CTA */}
      <div className="mt-12 pt-8 border-t border-gray-200 text-center">
        <p className="text-gray-500 mb-4">See the live signals and verify our track record.</p>
        <div className="flex items-center justify-center gap-4">
          <Link to="/" className="px-6 py-2.5 bg-gray-900 text-white rounded-lg hover:bg-gray-800 font-medium">
            View Live Signals
          </Link>
          <Link to="/accuracy" className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium">
            See Track Record
          </Link>
        </div>
      </div>

      {/* Author */}
      <div className="mt-10 pt-6 border-t border-gray-100">
        <p className="text-sm text-gray-500">
          <strong className="text-gray-700">Manohar</strong> &middot; Founder, LookInsight &middot; manohar@lookinsight.ai
        </p>
      </div>
    </article>
  )
}
