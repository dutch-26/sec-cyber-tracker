export const revalidate = 86400;

export default function MethodologyPage() {
  return (
    <div className="max-w-3xl space-y-10">
      <div>
        <h1 className="text-2xl font-bold text-white">Methodology</h1>
        <p className="text-slate-400 mt-2">
          How data is sourced, processed, and analyzed for this tracker.
        </p>
      </div>

      <Section title="Data Source: SEC EDGAR">
        <p>
          All incidents originate from Form 8-K filings disclosing a material cybersecurity incident
          under <strong>Item 1.05</strong> — the reporting obligation introduced by the SEC&apos;s
          Cybersecurity Disclosure Rules, effective December 18, 2023.
        </p>
        <p>
          Filings are retrieved via the{" "}
          <a href="https://efts.sec.gov/LATEST/search-index" className="text-blue-400 hover:text-blue-300" target="_blank" rel="noopener noreferrer">
            EDGAR Full-Text Search API
          </a>{" "}
          using the query <code className="text-orange-300 text-sm bg-slate-800 px-1 rounded">&quot;Item 1.05&quot;</code> filtered
          to Form 8-K filings. Company tickers are resolved via SEC&apos;s{" "}
          <code className="text-orange-300 text-sm bg-slate-800 px-1 rounded">company_tickers.json</code> mapping file.
          Foreign private issuers without a US exchange ticker are excluded.
        </p>
      </Section>

      <Section title="Stock Price Data">
        <p>
          Historical daily closing prices are retrieved via{" "}
          <a href="https://pypi.org/project/yfinance/" className="text-blue-400 hover:text-blue-300" target="_blank" rel="noopener noreferrer">
            yfinance
          </a>{" "}
          (Yahoo Finance). All prices are split/dividend adjusted.
        </p>
        <ul className="list-disc list-inside space-y-1 text-slate-300">
          <li><strong>Baseline (T-1):</strong> Closing price on the last trading day before the 8-K filing date</li>
          <li><strong>T+0:</strong> Closing price on the filing date itself</li>
          <li><strong>T+30, T+60, T+90:</strong> Closing prices approximately 30, 60, and 90 calendar days post-filing</li>
        </ul>
        <p className="text-sm text-slate-500 mt-2">
          If no trading occurred on the exact target date (weekend/holiday), the next available
          trading day within 5 days is used.
        </p>
      </Section>

      <Section title="Peer Group Comparison">
        <p>
          Each company is classified by GICS sector (via yfinance) and market cap tier:
        </p>
        <ul className="list-disc list-inside space-y-1 text-slate-300">
          <li><strong>Small:</strong> Market cap &lt; $2B</li>
          <li><strong>Mid:</strong> $2B – $10B</li>
          <li><strong>Large:</strong> &gt; $10B</li>
        </ul>
        <p>
          The peer return benchmark is the corresponding{" "}
          <strong>SPDR Select Sector ETF</strong> return over the same calendar window as the
          incident (e.g., XLK for Information Technology, XLF for Financials). This provides a
          liquid, transparent, and widely-recognized proxy for sector performance.
        </p>
        <p>
          <strong>Alpha</strong> = company return − sector ETF return at each interval. A negative
          alpha indicates the company underperformed its sector peers.
        </p>
        <p className="text-sm text-slate-500">
          Limitation: sector ETFs do not control for individual company-level factors unrelated to
          the incident. Peer comparison is indicative, not causal.
        </p>
      </Section>

      <Section title="10-K Item 1A Risk Analysis">
        <p>
          For each incident, the most recent annual report (Form 10-K) filed{" "}
          <em>before</em> the incident 8-K date is retrieved from EDGAR. The Item 1A (Risk Factors)
          section is extracted by locating the &quot;Item 1A&quot; heading and reading through to &quot;Item 1B&quot;
          or &quot;Item 2&quot;.
        </p>
        <p>
          Item 1A text and the 8-K incident description are then sent to{" "}
          <strong>Claude (claude-sonnet-4-6, Anthropic)</strong> with the following prompt tasks:
        </p>
        <ol className="list-decimal list-inside space-y-1 text-slate-300">
          <li>Classify which cyber risk types appear meaningfully in Item 1A</li>
          <li>Classify the incident type from the 8-K description</li>
          <li>Determine whether the incident risk type was predicted (bool + confidence 0–1)</li>
          <li>Provide a 1–2 sentence explanation citing specific language if applicable</li>
        </ol>
        <p>
          Risk type taxonomy: ransomware · data breach/exfiltration · nation-state/APT ·
          third-party/supply chain · insider threat · DDoS/availability · OT/ICS/operational ·
          credential compromise/phishing · zero-day/vulnerability exploitation ·
          business email compromise · other
        </p>
        <p className="text-sm text-slate-500">
          Limitation: Item 1A risk disclosures are often generic boilerplate. The confidence
          score distinguishes between specific, targeted disclosures (high confidence) and
          generic coverage (low confidence). The &quot;predicted&quot; determination requires the disclosure
          to go beyond standard boilerplate to be classified as true.
        </p>
      </Section>

      <Section title="Update Cadence">
        <p>
          The data pipeline runs daily via GitHub Actions, checking for new Item 1.05 8-K filings
          filed since the last run. New incidents are processed incrementally — existing records are
          not re-fetched unless a full refresh is triggered. The Vercel deployment automatically
          rebuilds when updated data is committed to the repository.
        </p>
      </Section>

      <Section title="Limitations & Disclaimers">
        <ul className="list-disc list-inside space-y-1 text-slate-300">
          <li>Not all Item 1.05 filings describe true &quot;material&quot; incidents — some companies file out of caution</li>
          <li>yfinance data may have gaps or inaccuracies for thinly-traded securities</li>
          <li>Claude&apos;s analysis is probabilistic and may misclassify edge cases</li>
          <li>Stock price moves reflect many factors beyond the cyber incident</li>
          <li><strong>This is not investment advice.</strong></li>
        </ul>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-white border-b border-slate-800 pb-2">{title}</h2>
      <div className="space-y-3 text-slate-300 text-sm leading-relaxed">{children}</div>
    </section>
  );
}
