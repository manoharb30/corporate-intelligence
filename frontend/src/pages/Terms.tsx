export default function Terms() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12 prose prose-slate">
      <h1 className="text-3xl font-bold mb-2">Terms of Service</h1>
      <p className="text-sm text-slate-500 mb-8">Last updated: May 14, 2026</p>

      <p className="mb-6">
        These Terms govern your use of the LookInsight website at{' '}
        <a href="https://ci.lookinsight.ai" className="text-blue-600 underline">
          ci.lookinsight.ai
        </a>{' '}
        and the LookInsight MCP connector. By accessing the service or installing the connector,
        you agree to be bound by these Terms.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">1. Informational purposes only — not financial advice</h2>
      <p className="mb-6">
        The signals, statistics, and explanations presented by LookInsight are derived from public
        SEC filings and public market data for research and informational purposes only. Nothing
        on the website, in the connector, or in any response from our tools constitutes investment
        advice, a recommendation to buy or sell any security, or a solicitation of any kind. You
        are solely responsible for your own investment decisions, and you should consult a
        qualified financial professional before acting on any information surfaced by the service.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">2. No warranty</h2>
      <p className="mb-6">
        The service is provided <strong>"as is"</strong> and <strong>"as available"</strong>,
        without any warranty of any kind, express or implied — including but not limited to
        warranties of accuracy, completeness, merchantability, fitness for a particular purpose,
        and non-infringement. Past performance does not guarantee future results. We do not warrant
        that the service will be uninterrupted, error-free, secure, or free from harmful
        components.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">3. Acceptable use</h2>
      <p className="mb-3">You agree not to:</p>
      <ul className="list-disc pl-6 mb-6">
        <li>Use the service in any way that violates applicable law</li>
        <li>Attempt to gain unauthorized access to the service or its underlying infrastructure</li>
        <li>Scrape, mirror, or systematically extract data outside the rate limits and patterns supported by the provided tools</li>
        <li>Re-distribute LookInsight outputs as your own data product without written permission</li>
        <li>Use the service to harass, deceive, or harm others, or to circumvent the safety annotations of any tool</li>
      </ul>

      <h2 className="text-xl font-semibold mt-8 mb-3">4. Data and accounts</h2>
      <p className="mb-6">
        Data collected via the LookInsight MCP connector is handled in accordance with our{' '}
        <a href="/privacy" className="text-blue-600 underline">Privacy Policy</a>. You authenticate
        with the connector using your GitHub account; you are responsible for keeping those
        credentials secure. We may suspend or revoke access for accounts found to be in violation
        of these Terms.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">5. Intellectual property</h2>
      <p className="mb-6">
        Underlying SEC filings and market data are public information from their respective
        sources. The LookInsight signal methodology, classifications, scoring, and the design of
        this website and the connector are proprietary to LookInsight. You receive a limited,
        non-exclusive, non-transferable license to use the service for personal or internal
        business research; you may not sublicense, resell, or build a competing data product on
        top of LookInsight outputs.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">6. Changes to the service or these Terms</h2>
      <p className="mb-6">
        We may modify the service, the connector, or these Terms at any time. Material changes
        will be reflected in the "Last updated" date above. Continued use after a change
        constitutes acceptance of the revised Terms.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">7. Limitation of liability</h2>
      <p className="mb-6">
        To the maximum extent permitted by law, LookInsight, its founders, contributors, and
        service providers will not be liable for any indirect, incidental, special, consequential,
        or punitive damages — including but not limited to trading losses, lost profits, or loss
        of data — arising out of or related to your use of the service, even if advised of the
        possibility of such damages.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">8. Contact</h2>
      <p className="mb-6">
        Questions about these Terms:{' '}
        <a href="mailto:manohar@lookinsight.ai" className="text-blue-600 underline">
          manohar@lookinsight.ai
        </a>
        .
      </p>
    </div>
  );
}
