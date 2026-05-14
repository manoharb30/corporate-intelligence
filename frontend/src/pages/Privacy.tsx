export default function Privacy() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12 prose prose-slate">
      <h1 className="text-3xl font-bold mb-2">Privacy Policy</h1>
      <p className="text-sm text-slate-500 mb-8">Last updated: May 14, 2026</p>

      <p className="mb-6">
        LookInsight ("we", "us") operates the website at{' '}
        <a href="https://ci.lookinsight.ai" className="text-blue-600 underline">
          ci.lookinsight.ai
        </a>{' '}
        and the LookInsight MCP connector at{' '}
        <code className="text-sm">lookinsight-mcp.lookinsight-ai.workers.dev</code>. This policy
        explains what we collect, why, and how we handle it.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">1. Public website (ci.lookinsight.ai)</h2>
      <p className="mb-6">
        The public website displays SEC Form 4 insider buying signals and aggregate performance
        statistics. It does not require an account and does not collect personal information from
        visitors. Cloudflare and Vercel may log standard request metadata (IP address, user agent,
        timestamps) for operational and abuse-prevention purposes.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">2. LookInsight MCP connector</h2>
      <p className="mb-3">
        When you install the LookInsight connector in Claude or another MCP-compatible client and
        sign in with GitHub, we receive the following from GitHub via OAuth 2.1:
      </p>
      <ul className="list-disc pl-6 mb-3">
        <li>your GitHub login (username)</li>
        <li>your display name</li>
        <li>your primary email address</li>
        <li>an OAuth access token scoped to <code>read:user</code></li>
      </ul>
      <p className="mb-6">
        These values are stored only as long as your MCP session is active. OAuth state and tokens
        live in Cloudflare KV with short TTLs and are encrypted at rest. We do not write them to
        any persistent database. The connector calls the LookInsight backend on your behalf to
        return signal data; user identity is not associated with backend queries.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">3. Data we do not collect</h2>
      <ul className="list-disc pl-6 mb-6">
        <li>The contents of your Claude conversations</li>
        <li>Your Claude account information</li>
        <li>Any files, prompts, or memory beyond what is required to fulfil a tool call</li>
        <li>Repository data, GitHub activity, or any other resource beyond the public profile fields above</li>
      </ul>

      <h2 className="text-xl font-semibold mt-8 mb-3">4. Sharing and third parties</h2>
      <p className="mb-6">
        We do not sell, rent, or share personal information. Infrastructure providers — Cloudflare
        (Workers, KV), Vercel (frontend hosting), Railway (backend hosting), and GitHub (OAuth
        identity) — process data on our behalf strictly as required to operate the service.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">5. Data sources</h2>
      <p className="mb-6">
        Signal data is derived from public SEC EDGAR filings (Form 4) and public market data via
        yfinance. No private or non-public information is involved.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">6. Your choices</h2>
      <p className="mb-6">
        You can revoke the LookInsight MCP connector at any time from your Claude settings or by
        revoking the GitHub OAuth grant at{' '}
        <a
          href="https://github.com/settings/applications"
          className="text-blue-600 underline"
          target="_blank"
          rel="noreferrer"
        >
          github.com/settings/applications
        </a>
        . Active session tokens are invalidated automatically when their TTL expires; you may also
        contact us to request deletion of any data we hold.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-3">7. Contact</h2>
      <p className="mb-6">
        Questions about this policy: <a href="mailto:manohar@lookinsight.ai" className="text-blue-600 underline">manohar@lookinsight.ai</a>.
      </p>
    </div>
  );
}
