import styles from "./search-histogram.module.css";
import type { HistogramPayload } from "../../lib/op-api";

// MARK: Component
interface SearchHistogramProps {
  histogram: HistogramPayload;
}

export function SearchHistogram({ histogram }: SearchHistogramProps) {
  if (!histogram || histogram.values.length === 0) {
    return null;
  }
  const maxValue = Math.max(...histogram.values);
  if (maxValue === 0) {
    return null;
  }

  return (
    <section className={styles.container} aria-label="Search activity by year">
      <h2 className={styles.heading}>Mentions over time</h2>
      <ul className={styles.list}>
        {histogram.years.map((year, index) => {
          const value = histogram.values[index] ?? 0;
          const widthPercent = Math.round((value / maxValue) * 100);
          return (
            <li key={year} className={styles.row}>
              <span>{year}</span>
              <span className={styles.bar} style={{ width: `${widthPercent}%` }} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
