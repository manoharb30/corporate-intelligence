export default function McpDocs() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-2">LookInsight MCP Connector</h1>
      <p className="text-sm text-slate-500 mb-8">For Claude and other MCP-compatible clients</p>

      <p className="mb-6 text-slate-700">
        The LookInsight MCP connector lets Claude (and any client speaking the Model Context
        Protocol) query LookInsight's live insider buying signals directly inside a conversation.
        Ask about hit rates, recent strong_buy signals, or the full evidence behind any signal —
        Claude calls our backend and surfaces the answer with citations.
      </p>

      <h2 className="text-xl font-semibold mt-10 mb-3">Install in Claude</h2>
      <ol className="list-decimal pl-6 space-y-2 mb-6">
        <li>Open Claude → <strong>Settings → Connectors</strong></li>
        <li>Click <strong>Add custom connector</strong></li>
        <li>
          Paste this server URL:
          <pre className="mt-2 bg-slate-100 rounded p-3 text-sm overflow-x-auto">
            https://lookinsight-mcp.lookinsight-ai.workers.dev/mcp
          </pre>
        </li>
        <li>Click <strong>Connect</strong>, sign in with GitHub, approve the consent dialog</li>
        <li>Open a new chat and try: <em>"What's LookInsight's current hit rate?"</em></li>
      </ol>

      <h2 className="text-xl font-semibold mt-10 mb-3">Tools exposed</h2>

      <div className="space-y-5 mb-8">
        <div>
          <h3 className="font-semibold text-slate-900">
            <code>get_recent_signals</code>
            <span className="ml-2 text-xs uppercase tracking-wide text-emerald-700 bg-emerald-50 rounded px-2 py-0.5">
              read-only
            </span>
          </h3>
          <p className="text-slate-700 mt-1">
            Lists recent strong_buy signals — multi-insider open-market clusters that pass our
            $100K + midcap + earnings-proximity filter. Returns ticker, signal date, cluster value,
            buyer count, market cap, and the accession number for follow-up.
          </p>
          <p className="text-sm text-slate-500 mt-1">
            Parameters: <code>days</code> (1–90, default 30).
          </p>
        </div>

        <div>
          <h3 className="font-semibold text-slate-900">
            <code>get_signal_detail</code>
            <span className="ml-2 text-xs uppercase tracking-wide text-emerald-700 bg-emerald-50 rounded px-2 py-0.5">
              read-only
            </span>
          </h3>
          <p className="text-slate-700 mt-1">
            Returns the full evidence for one signal: buyer list with titles, share counts and
            prices; the underlying Form 4 filings; entry price; current return; and SPY-relative
            performance.
          </p>
          <p className="text-sm text-slate-500 mt-1">
            Parameters: <code>accession_number</code> (from <code>get_recent_signals</code>).
          </p>
        </div>

        <div>
          <h3 className="font-semibold text-slate-900">
            <code>get_performance</code>
            <span className="ml-2 text-xs uppercase tracking-wide text-emerald-700 bg-emerald-50 rounded px-2 py-0.5">
              read-only
            </span>
          </h3>
          <p className="text-slate-700 mt-1">
            Returns headline track-record stats: total matured signals, hit rate, average return,
            average alpha vs SPY, beat-SPY percentage. Updated as signals mature.
          </p>
          <p className="text-sm text-slate-500 mt-1">No parameters.</p>
        </div>
      </div>

      <h2 className="text-xl font-semibold mt-10 mb-3">What is a "signal"?</h2>
      <p className="mb-6 text-slate-700">
        A <strong>strong_buy</strong> signal fires when, on a given date for a given company, all
        of the following hold: 2+ distinct insiders made GENUINE open-market P transactions,
        $100K+ total cluster value, $300M–$5B historical market cap (midcap), and within 60 days
        of the next earnings release. Returns are measured from the filing date (actionable) for a
        90-day horizon, benchmarked against SPY. Signal universe and methodology are described on
        the main site.
      </p>

      <h2 className="text-xl font-semibold mt-10 mb-3">Authentication</h2>
      <p className="mb-6 text-slate-700">
        The connector uses OAuth 2.1 with GitHub as the upstream identity provider. We request
        only the <code>read:user</code> scope and use your GitHub identity solely to authorize the
        MCP session. We don't read repositories, organizations, or any other GitHub data. See our{' '}
        <a href="/privacy" className="text-blue-600 underline">privacy policy</a> for full
        details.
      </p>

      <h2 className="text-xl font-semibold mt-10 mb-3">Troubleshooting</h2>
      <div className="space-y-4 mb-8 text-slate-700">
        <div>
          <p className="font-semibold text-slate-900">"Authorization with the MCP server failed" after approving</p>
          <p>
            Disconnect and re-add the connector in <strong>Settings → Connectors</strong>. If the
            error repeats, sign out of GitHub in the same browser, then retry — stale cookies from
            another GitHub account can mis-route the OAuth flow.
          </p>
        </div>
        <div>
          <p className="font-semibold text-slate-900">Tools don't appear after connecting</p>
          <p>
            Open a <em>new</em> chat in Claude — the connector tools are loaded at conversation
            start. Existing chats opened before installation won't see the new tools.
          </p>
        </div>
        <div>
          <p className="font-semibold text-slate-900"><code>get_signal_detail</code> returns "not found"</p>
          <p>
            The <code>accession_number</code> argument must be the exact string returned by{' '}
            <code>get_recent_signals</code> (e.g.{' '}
            <code>CLUSTER-1234567-2026-04-15</code>) — not a ticker, not an SEC accession.
          </p>
        </div>
        <div>
          <p className="font-semibold text-slate-900">Numbers don't match the public dashboard</p>
          <p>
            The dashboard caches snapshots; the MCP tools call the live aggregate endpoint.
            Differences of one or two signals on the same day are expected during the cache
            window. If the gap persists for more than 24h, contact support.
          </p>
        </div>
        <div>
          <p className="font-semibold text-slate-900">Revoking access</p>
          <p>
            Disconnect from <strong>Settings → Connectors</strong> in Claude. To fully revoke at
            the GitHub layer, visit{' '}
            <a
              href="https://github.com/settings/applications"
              className="text-blue-600 underline"
              target="_blank"
              rel="noreferrer"
            >
              github.com/settings/applications
            </a>
            .
          </p>
        </div>
      </div>

      <h2 className="text-xl font-semibold mt-10 mb-3">Support</h2>
      <p className="mb-6 text-slate-700">
        Questions, bug reports, or feature requests:{' '}
        <a href="mailto:manohar@lookinsight.ai" className="text-blue-600 underline">
          manohar@lookinsight.ai
        </a>
        .
      </p>
    </div>
  );
}
