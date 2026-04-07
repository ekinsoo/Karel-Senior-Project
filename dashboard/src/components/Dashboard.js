import React, { useContext } from "react";
import { IoTContext } from "../context/IoTContext";
import Header from "./Header";
import CameraFeed from "./CameraFeed";
import SensorMonitoring from "./SensorMonitoring";
import DefectDetection from "./DefectDetection";
import SystemStatus from "./SystemStatus";
import Statistics from "./Statistics";
import AlertPanel from "./AlertPanel";
import QRScanner from "./QRScanner";
import EnvironmentalPanel from "./EnvironmentalPanel";
import "../styles/Dashboard.css";

function Dashboard() {
  const { cameraData, sensorData, qrHistory, envData, envHistory, defectionData, systemStatus, statistics, alerts, cameraMode, captureLoading, switchCameraMode, triggerCapture } =
    useContext(IoTContext);

  return (
    <div className="iot-dashboard">
      <Header systemStatus={systemStatus} />

      <div className="dashboard-container">
        <div className="dashboard-content">
          {/* Top Row: Camera Feed & Alerts */}
          <div className="row g-3 mb-4">
            <div className="col-12 col-lg-8">
              <CameraFeed
                cameraData={cameraData}
                defectionData={defectionData}
                cameraMode={cameraMode}
                captureLoading={captureLoading}
                onModeSwitch={switchCameraMode}
                onCapture={triggerCapture}
              />
            </div>
            <div className="col-12 col-lg-4">
              <AlertPanel alerts={alerts} />
            </div>
          </div>

          {/* Environmental + QR Scanner Row */}
          <div className="row g-3 mb-4">
            <div className="col-12 col-lg-6">
              <EnvironmentalPanel envData={envData} envHistory={envHistory} />
            </div>
            <div className="col-12 col-lg-6">
              <QRScanner qrHistory={qrHistory} sensorData={sensorData} />
            </div>
          </div>

          {/* Middle Row: Sensors & Defect Detection */}
          <div className="row g-3 mb-4">
            <div className="col-12 col-md-6 col-lg-3">
              <SensorMonitoring sensorData={sensorData} />
            </div>
            <div className="col-12 col-md-6 col-lg-3">
              <DefectDetection defectionData={defectionData} />
            </div>
            <div className="col-12 col-md-6 col-lg-3">
              <Statistics statistics={statistics} />
            </div>
            <div className="col-12 col-md-6 col-lg-3">
              <SystemStatus systemStatus={systemStatus} />
            </div>
          </div>

          {/* Bottom Row: Detailed Stats */}
          <div className="row g-3">
            <div className="col-12">
              <div className="stats-detail-grid">
                <div className="stat-detail-card">
                  <span className="stat-label">Total Inspected</span>
                  <span className="stat-value">{statistics.totalInspected}</span>
                </div>
                <div className="stat-detail-card">
                  <span className="stat-label">Defects Found</span>
                  <span className="stat-value">{statistics.defectsFound}</span>
                </div>
                <div className="stat-detail-card">
                  <span className="stat-label">Defect Rate</span>
                  <span className="stat-value">{statistics.defectRate}%</span>
                </div>
                <div className="stat-detail-card">
                  <span className="stat-label">Avg Process Time</span>
                  <span className="stat-value">{statistics.averageProcessTime}s</span>
                </div>
                <div className="stat-detail-card">
                  <span className="stat-label">Today's Defects</span>
                  <span className="stat-value">{statistics.todayDefects}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="iot-footer">
        <span className="footer-text">
          © {new Date().getFullYear()} Karel SmartHub Dashboard
        </span>
      </footer>
    </div>
  );
}

export default Dashboard;
