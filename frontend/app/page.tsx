import { HomePage } from "../components/home/home-page";
import { TrueCivicApiClient } from "../lib/op-api";

export default async function Home() {
  const client = TrueCivicApiClient.fromEnv();
  try {
    const payload = await client.fetchHome();
    return <HomePage payload={payload} />;
  } catch (error) {
    return (
      <main className="site-main">
        <section className="home-section">
          <div className="layout-row">
            <div className="layout-primary">
              <h1>truecivic</h1>
              <p>We could not load the homepage data right now. Please try again soon.</p>
              {process.env.NODE_ENV !== "production" ? (
                <pre className="error-block">{String(error)}</pre>
              ) : null}
            </div>
          </div>
        </section>
      </main>
    );
  }
}
