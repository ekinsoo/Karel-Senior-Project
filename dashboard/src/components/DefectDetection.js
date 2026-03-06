import React from "react";

function DefectDetection({ defectionData }) {
  const getStatusColor = () => {
    if (defectionData.defectDetected) {
      if (defectionData.confidence > 80) return "#d9534f";
      return "#e8a838";
    }
    return "#47b881";
  };

  const getStatusLabel = () => {
    if (defectionData.defectDetected) {
      if (defectionData.confidence > 80) return "CRITICAL";
      return "WARNING";
    }
    return "PASS";
  };

  return (
    <div className="defect-card">
      <div className="card-header">
        <h6 className="card-title">Defect Detection</h6>
      </div>

      <div className="card-content">
        <div className="defect-status-large">
          <div className="status-circle" style={{ borderColor: getStatusColor() }}>
            <div
              className="status-pulse"
              style={{
                backgroundColor: getStatusColor(),
              }}
            ></div>
            <span className="status-text">{getStatusLabel()}</span>
          </div>
        </div>

        {defectionData.defectDetected && (
          <>
            <div className="defect-detail">
              <span className="detail-label">Confidence</span>
              <div className="confidence-bar">
                <div
                  className="confidence-fill"
                  style={{
                    width: `${defectionData.confidence}%`,
                    backgroundColor: getStatusColor(),
                  }}
                ></div>
              </div>
              <span className="confidence-value">{defectionData.confidence}%</span>
            </div>

            <div className="defect-counter">
              <span className="counter-label">Defects This Session</span>
              <span className="counter-value">{defectionData.defectCount}</span>
            </div>
          </>
        )}

        {!defectionData.defectDetected && (
          <div className="no-defect-message">
            <span>✓ No defects detected</span>
            <span className="secondary">Last check: Just now</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default DefectDetection;
