import React from "react";

function QRScanner({ qrHistory, sensorData }) {
  return (
    <div className="qr-scanner-card">
      <div className="card-header">
        <h6 className="card-title">QR / DataMatrix Scanner</h6>
        <span className="qr-history-count">{qrHistory.length}</span>
      </div>

      <div className="card-content">
        {/* Latest QR Result */}
        <div className="qr-latest-section">
          <span className="qr-section-label">LATEST SCAN</span>
          {sensorData.qrCode && sensorData.qrCode !== "-" ? (
            <div className="qr-latest-result">
              <div className="qr-data-display">
                <span className="qr-decoded-text">{sensorData.qrCode}</span>
              </div>
              <div className="qr-meta-row">
                <span className="qr-meta-time">{sensorData.qrScannedTime}</span>
              </div>
            </div>
          ) : (
            <div className="qr-no-data">
              <span className="qr-no-data-text">Waiting for scan...</span>
            </div>
          )}
        </div>

        {/* QR History */}
        {qrHistory.length > 0 && (
          <div className="qr-history-section">
            <span className="qr-section-label">RECENT HISTORY</span>
            <div className="qr-history-list">
              {qrHistory.slice(0, 10).map((item, idx) => (
                <div key={idx} className="qr-history-item">
                  <div className="qr-history-data">
                    <span className="qr-history-text">{item.data}</span>
                    <span className="qr-history-meta">
                      {item.code_type} · {item.method} · {item.elapsed_ms} ms
                    </span>
                  </div>
                  <span className="qr-history-time">{item.timestamp}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default QRScanner;
