import React from "react";

function CameraFeed({ cameraData, defectionData, cameraMode, captureLoading, onModeSwitch, onCapture }) {
  const getDefectColor = () => {
    if (!defectionData.defectDetected) return "#47b881";
    if (defectionData.confidence > 80) return "#d9534f";
    return "#e8a838";
  };

  const getDefectLabel = () => {
    const defectMap = {
      solder_joint: "Solder Joint Issue",
      copper_trace: "Copper Trace Defect",
      component_missing: "Missing Component",
      none: "No Defect",
    };
    return defectMap[defectionData.defectType] || "Unknown";
  };

  const isLive = cameraMode === "live";

  return (
    <div className="camera-feed-card">
      <div className="feed-header">
        <div className="header-left">
          <h5 className="feed-title">
            <span className={`live-dot ${isLive ? "" : "dot-capture"}`}></span>
            {isLive ? "Live Feed" : "Capture Mode"}
          </h5>
          <span className="feed-subtitle">IMX219-160 | 1920×1080</span>
        </div>
        <div className="header-right">
          {/* Mode Toggle */}
          <div className="mode-toggle">
            <button
              className={`mode-btn ${isLive ? "mode-btn-active" : ""}`}
              onClick={() => onModeSwitch("live")}
            >
              ● LIVE
            </button>
            <button
              className={`mode-btn ${!isLive ? "mode-btn-active" : ""}`}
              onClick={() => onModeSwitch("capture")}
            >
              ◎ CAPTURE
            </button>
          </div>
          <span className="timestamp">{cameraData.timestamp}</span>
        </div>
      </div>

      <div className="feed-wrapper">
        <img
          src={cameraData.imageSrc}
          alt="PCB camera feed"
          className="feed-image"
          onError={(e) => {
            e.target.src =
              "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E%3Crect fill='%23222' width='800' height='600'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='.3em' fill='%23666' font-size='24'%3ECamera Offline%3C/text%3E%3C/svg%3E";
          }}
        />

        {/* Capture button overlay (only in capture mode) */}
        {!isLive && (
          <div className="capture-overlay">
            <button
              className={`capture-btn ${captureLoading ? "capture-btn-loading" : ""}`}
              onClick={onCapture}
              disabled={captureLoading}
            >
              {captureLoading ? (
                <>
                  <span className="capture-spinner"></span>
                  Capturing...
                </>
              ) : (
                <>📸 Capture Frame</>
              )}
            </button>
          </div>
        )}

        {/* Mode badge */}
        <div className={`mode-badge ${isLive ? "mode-badge-live" : "mode-badge-capture"}`}>
          {isLive ? "● LIVE" : "◎ CAPTURE"}
        </div>

        {/* Defect Overlay */}
        {defectionData.defectDetected && (
          <div className="defect-overlay">
            <div className="defect-badge" style={{ borderColor: getDefectColor() }}>
              <span className="defect-pulse"></span>
              <span className="defect-text">DEFECT DETECTED</span>
            </div>
          </div>
        )}
      </div>

      <div className="feed-footer">
        <div className="footer-info">
          <span className="frame-count">Frame #{cameraData.frameCount}</span>
          <span className="frame-rate">
            {isLive ? "LIVE STREAM" : "ON-DEMAND"}
          </span>
        </div>
        <div className="defect-info">
          <span
            className="defect-status"
            style={{
              color: defectionData.defectDetected ? getDefectColor() : "#47b881",
            }}
          >
            {defectionData.defectDetected ? "● DEFECT" : "● OK"}
          </span>
        </div>
      </div>

      {/* Defect Details */}
      {defectionData.defectDetected && (
        <div className="defect-details">
          <div className="detail-row">
            <span className="detail-label">Defect Type:</span>
            <span className="detail-value">{getDefectLabel()}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Confidence:</span>
            <span className="detail-value">{defectionData.confidence}%</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Detected:</span>
            <span className="detail-value">{defectionData.lastDefectTime}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default CameraFeed;
