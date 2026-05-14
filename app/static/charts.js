window.EduTraceCharts = (() => {
  const STORAGE_KEY = "edutrace-chart-variant";
  const palettes = {
    academic: ["#2563eb", "#0ea5e9", "#14b8a6", "#22c55e", "#f59e0b", "#f97316"],
    compare: ["#2563eb", "#8b5cf6", "#ec4899", "#f97316", "#14b8a6", "#84cc16"],
    warm: ["#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16", "#22c55e"]
  };

  function savedVariant() {
    try {
      const value = window.localStorage.getItem(STORAGE_KEY);
      if (value && palettes[value]) {
        return value;
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  function colorFor(index, variant) {
    const scheme = palettes[variant] || palettes.academic;
    return scheme[index % scheme.length];
  }

  function normalizeDatasets(datasets, variant) {
    return datasets.map((dataset, index) => {
      const color = dataset.backgroundColor || colorFor(index, variant);
      return {
        borderRadius: 8,
        borderSkipped: false,
        barThickness: "flex",
        maxBarThickness: 28,
        ...dataset,
        backgroundColor: color,
        borderColor: dataset.borderColor || color,
        borderWidth: dataset.borderWidth || 1
      };
    });
  }

  function createBarChart(canvasId, labels, datasets, config = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") {
      return null;
    }
    const explicitHeight = Number(canvas.getAttribute("height") || 0);
    if (!canvas.style.height && explicitHeight > 0) {
      canvas.style.height = `${explicitHeight}px`;
    }
    const max = config.max ?? 100;
    const variant = savedVariant() || config.variant || "academic";
    const normalized = normalizeDatasets(datasets, variant);

    return new Chart(canvas, {
      type: "bar",
      data: { labels, datasets: normalized },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: config.aspectRatio || 2.2,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            labels: {
              color: "#334155",
              boxWidth: 12,
              boxHeight: 12,
              usePointStyle: true,
              pointStyle: "rectRounded"
            }
          },
          tooltip: {
            backgroundColor: "#0f172a",
            titleColor: "#f8fafc",
            bodyColor: "#e2e8f0",
            cornerRadius: 10,
            padding: 10
          }
        },
        scales: {
          x: {
            ticks: { color: "#475569", maxRotation: 30, minRotation: 0 },
            grid: { display: false }
          },
          y: {
            beginAtZero: true,
            max,
            ticks: { color: "#475569" },
            grid: { color: "rgba(148, 163, 184, 0.25)" }
          }
        }
      }
    });
  }

  return { createBarChart };
})();
