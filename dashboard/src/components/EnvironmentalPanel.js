import React from "react";

function EnvironmentalPanel({ envData, envHistory }) {
  const hasData = envData && envData.temp_c !== null;

  const getTempColor = () => {
    if (!hasData) return "#6b7280";
    const t = envData.temp_c;
    if (t <= 25) return "#47b881";        // green – normal
    if (t <= 30) {
      // green → amber gradient (25-30°C)
      const ratio = (t - 25) / 5;
      const r = Math.round(0x47 + (0xe8 - 0x47) * ratio);
      const g = Math.round(0xb8 + (0xa8 - 0xb8) * ratio);
      const b = Math.round(0x81 + (0x38 - 0x81) * ratio);
      return `rgb(${r},${g},${b})`;
    }
    if (t <= 40) {
      // amber → red gradient (30-40°C)
      const ratio = (t - 30) / 10;
      const r = Math.round(0xe8 + (0xd9 - 0xe8) * ratio);
      const g = Math.round(0xa8 + (0x53 - 0xa8) * ratio);
      const b = Math.round(0x38 + (0x4f - 0x38) * ratio);
      return `rgb(${r},${g},${b})`;
    }
    return "#d9534f";                     // red – critical
  };

  const getHumColor = () => {
    if (!hasData) return "#6b7280";
    if (envData.hum_pct > 70 || envData.hum_pct < 20) return "#e8a838";
    return "#5bbfcf";
  };

  const getPressColor = () => {
    if (!hasData) return "#6b7280";
    return "#4a90d9";
  };

  const formatTime = (iso) => {
    if (!iso) return "--";
    try {
      return new Date(iso).toLocaleTimeString();
    } catch {
      return iso;
    }
  };

  return (
    <div className="env-panel-card">
      <div className="card-header">
        <h6 className="card-title">Environmental</h6>
        {hasData && (
          <span className="card-badge">{envData.device_id || "BME280"}</span>
        )}
      </div>

      <div className="card-content">
        {!hasData ? (
          <div className="env-no-data">
            <span className="env-no-data-text">Waiting for BME280 data...</span>
          </div>
        ) : (
          <>
            {/* Three-column gauge layout */}
            <div className="env-gauges">
              <div className="env-gauge">
                <span className="env-gauge-label">Temperature</span>
                <span className="env-gauge-value" style={{ color: getTempColor() }}>
                  {envData.temp_c.toFixed(1)}
                </span>
                <span className="env-gauge-unit">°C</span>
                {envData.temp_c > 25 && (
                  <span className="env-gauge-warn" style={{ color: getTempColor() }}>
                    {envData.temp_c > 35 ? "CRITICAL" : "WARNING"}
                  </span>
                )}
                <div className="sensor-bar">
                  <div
                    className="sensor-bar-fill"
                    style={{
                      width: `${Math.min(100, Math.max(0, ((envData.temp_c - 10) / 50) * 100))}%`,
                      backgroundColor: getTempColor(),
                    }}
                  ></div>
                </div>
              </div>

              <div className="env-gauge">
                <span className="env-gauge-label">Humidity</span>
                <span className="env-gauge-value" style={{ color: getHumColor() }}>
                  {envData.hum_pct.toFixed(1)}
                </span>
                <span className="env-gauge-unit">%</span>
                <div className="sensor-bar">
                  <div
                    className="sensor-bar-fill"
                    style={{
                      width: `${Math.min(100, envData.hum_pct)}%`,
                      backgroundColor: getHumColor(),
                    }}
                  ></div>
                </div>
              </div>

              <div className="env-gauge">
                <span className="env-gauge-label">Pressure</span>
                <span className="env-gauge-value" style={{ color: getPressColor() }}>
                  {envData.press_hpa.toFixed(1)}
                </span>
                <span className="env-gauge-unit">hPa</span>
                <div className="sensor-bar">
                  <div
                    className="sensor-bar-fill"
                    style={{
                      width: `${Math.min(100, Math.max(0, ((envData.press_hpa - 950) / 100) * 100))}%`,
                      backgroundColor: getPressColor(),
                    }}
                  ></div>
                </div>
              </div>
            </div>

            {/* Footer: last update + seq */}
            <div className="env-footer">
              <span className="env-footer-time">
                Updated: {formatTime(envData.t_iso)}
              </span>
              {envData.seq != null && (
                <span className="env-footer-seq">seq #{envData.seq}</span>
              )}
            </div>

            {/* Mini history list */}
            {envHistory.length > 0 && (
              <div className="env-history">
                <span className="qr-section-label">Recent Readings</span>
                <div className="env-history-list">
                  {envHistory.slice(0, 8).map((item, idx) => (
                    <div key={idx} className="env-history-item">
                      <span className="env-hist-temp">{item.temp_c}°C</span>
                      <span className="env-hist-hum">{item.hum_pct}%</span>
                      <span className="env-hist-press">{item.press_hpa} hPa</span>
                      <span className="env-hist-time">{formatTime(item.t_iso)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default EnvironmentalPanel;
