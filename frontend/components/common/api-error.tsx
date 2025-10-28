interface ApiErrorProps {
  title: string;
  message: string;
  error: unknown;
}

export function ApiError({ title, message, error }: ApiErrorProps) {
  const showDetails = process.env.NODE_ENV !== "production";
  return (
    <main className="site-main">
      <section className="home-section">
        <div className="layout-row">
          <div className="layout-primary">
            <h1>{title}</h1>
            <p>{message}</p>
            {showDetails ? <pre className="error-block">{String(error)}</pre> : null}
          </div>
        </div>
      </section>
    </main>
  );
}
