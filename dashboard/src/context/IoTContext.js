import React, { createContext, useState, useEffect } from "react";

export const IoTContext = createContext();

// Dynamically resolve the API server — works whether the dashboard is
// opened on the Jetson itself (localhost) or from another machine on
// the local network (uses the Jetson's actual IP automatically).
const API_BASE = `http://${window.location.hostname}:8000`;

export const IoTDataProvider = ({ children }) => {
  const [cameraData, setCameraData] = useState({
    imageSrc: `${API_BASE}/api/latest-image`,
    timestamp: "-",
    frameCount: 0,
    fps: 0,
  });

  const [sensorData, setSensorData] = useState({
    temperature: null,
    temperatureStatus: "normal",
    humidity: null,
    qrCode: "-",
    qrScannedTime: "-",
  });

  const [qrHistory, setQrHistory] = useState([]);

  const [envData, setEnvData] = useState({
    temp_c: null,
    hum_pct: null,
    press_hpa: null,
    device_id: null,
    t_iso: null,
    received: null,
  });

  const [envHistory, setEnvHistory] = useState([]);

  const [defectionData, setDefectionData] = useState({
    defectCount: 0,
    defectDetected: false,
    confidence: 0,
    lastDefectTime: null,
    defectType: "none",
  });

  const [systemStatus, setSystemStatus] = useState({
    esp32Connected: false,
    cameraOnline: false,
    uptime: "-",
  });

  const [statistics, setStatistics] = useState({
    totalInspected: 0,
    defectsFound: 0,
    defectRate: 0,
    averageProcessTime: 0,
    todayDefects: 0,
  });

  const [alerts, setAlerts] = useState([]);

  // ── Camera mode state ───────────────────────────────────────────────────
  const [cameraMode, setCameraMode] = useState("live"); // "live" | "capture"
  const [captureLoading, setCaptureLoading] = useState(false);

  // Switch mode on the backend → Jetson
  const switchCameraMode = async (mode) => {
    try {
      const res = await fetch(`${API_BASE}/api/camera/mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      const data = await res.json();
      setCameraMode(data.mode);
    } catch (err) {
      console.error("Mode switch failed", err);
    }
  };

  // Request a single high-quality capture
  const triggerCapture = async () => {
    setCaptureLoading(true);
    try {
      await fetch(`${API_BASE}/api/camera/capture`, { method: "POST" });
      // Wait a moment for the frame to arrive, then refresh the image
      setTimeout(() => {
        setCameraData((prev) => ({
          ...prev,
          imageSrc: `${API_BASE}/api/latest-image?ts=${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
        }));
        setCaptureLoading(false);
      }, 1500);
    } catch (err) {
      console.error("Capture failed", err);
      setCaptureLoading(false);
    }
  };

  // Sync mode from server on load
  useEffect(() => {
    fetch(`${API_BASE}/api/camera/mode`)
      .then((r) => r.json())
      .then((d) => setCameraMode(d.mode))
      .catch(() => {});
  }, []);

  // Fetch camera image with cache busting (only in live mode)
  useEffect(() => {
    if (cameraMode !== "live") return; // no polling in capture mode

    const imageInterval = setInterval(() => {
      setCameraData((prev) => ({
        ...prev,
        imageSrc: `${API_BASE}/api/latest-image?ts=${Date.now()}`,
        timestamp: new Date().toLocaleTimeString(),
      }));
    }, 2000); // Update every 2 seconds

    return () => clearInterval(imageInterval);
  }, [cameraMode]);

  // Poll QR decode results from backend
  useEffect(() => {
    const qrInterval = setInterval(async () => {
      try {
        // Latest QR result → update sensorData
        const latestRes = await fetch(`${API_BASE}/api/qr-latest`);
        const latest = await latestRes.json();
        if (latest.data) {
          setSensorData((prev) => ({
            ...prev,
            qrCode: latest.data,
            qrScannedTime: latest.timestamp,
          }));
        }

        // QR history → update qrHistory state
        const histRes = await fetch(`${API_BASE}/api/qr-history`);
        const hist = await histRes.json();
        setQrHistory(hist);
      } catch (err) {
        // Backend unreachable — keep old data
      }
    }, 2000);

    return () => clearInterval(qrInterval);
  }, []);

  // Poll BME280 environmental data from backend
  useEffect(() => {
    const envInterval = setInterval(async () => {
      try {
        const latestRes = await fetch(`${API_BASE}/api/env/latest`);
        const latest = await latestRes.json();
        if (latest.temp_c !== undefined) {
          setEnvData(latest);
          // Also feed the existing sensorData for backward compatibility
          setSensorData((prev) => ({
            ...prev,
            temperature: latest.temp_c,
            humidity: latest.hum_pct,
            temperatureStatus:
              latest.temp_c > 35 ? "critical" : latest.temp_c > 25 ? "warning" : "normal",
          }));
          // Mark ESP32 as connected
          setSystemStatus((prev) => ({ ...prev, esp32Connected: true }));
        }

        const histRes = await fetch(`${API_BASE}/api/env/history`);
        const hist = await histRes.json();
        if (Array.isArray(hist)) {
          setEnvHistory(hist);
        }
      } catch (err) {
        // Backend unreachable
      }
    }, 2000);

    return () => clearInterval(envInterval);
  }, []);

  const value = {
    cameraData,
    sensorData,
    qrHistory,
    envData,
    envHistory,
    defectionData,
    systemStatus,
    statistics,
    alerts,
    cameraMode,
    captureLoading,
    switchCameraMode,
    triggerCapture,
    setSensorData,
    setDefectionData,
    setSystemStatus,
    setStatistics,
    setAlerts,
  };

  return (
    <IoTContext.Provider value={value}>{children}</IoTContext.Provider>
  );
};
