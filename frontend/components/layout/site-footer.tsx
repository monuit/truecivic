import Link from "next/link";

// MARK: Component
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__support">
        <span>a project by</span>
        <span className="site-footer__brand">truecivic</span>
      </div>
      <div className="site-footer__message">
        <p>
          <strong>This is not a government site.</strong>
          <br />
          Not even sort of.
        </p>
      </div>
      <div className="site-footer__links">
        <div>
          <strong>Words</strong>
          <Link href="/debates">Debates</Link>
          <Link href="/committees">Committees</Link>
          <Link href="/search">Search</Link>
          <Link href="/alerts">Alerts</Link>
        </div>
        <div>
          <strong>Laws</strong>
          <Link href="/bills">Bills</Link>
          <Link href="/votes">Votes</Link>
        </div>
        <div>
          <strong>More</strong>
          <Link href="/api">Developers</Link>
        </div>
      </div>
    </footer>
  );
}
