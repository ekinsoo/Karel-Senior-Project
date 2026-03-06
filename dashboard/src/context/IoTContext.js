import React, { createContext, useState, useEffect } from "react";

export const IoTContext = createContext();

export const IoTDataProvider = ({ children }) => {
  const [cameraData, setCameraData] = useState({
    imageSrc: "http://localhost:8000/api/latest-image",
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

  // Fetch camera image with cache busting
  useEffect(() => {
    const imageInterval = setInterval(() => {
      setCameraData((prev) => ({
        ...prev,
        imageSrc: `http://localhost:8000/api/latest-image?ts=${Date.now()}`,
        timestamp: new Date().toLocaleTimeString(),
      }));
    }, 2000); // Update every 2 seconds

    return () => clearInterval(imageInterval);
  }, []);

  // Poll QR decode results from backend
  useEffect(() => {
    const qrInterval = setInterval(async () => {
      try {
        // Latest QR result → update sensorData
        const latestRes = await fetch("http://localhost:8000/api/qr-latest");
        const latest = await latestRes.json();
        if (latest.data) {
          setSensorData((prev) => ({
            ...prev,
            qrCode: latest.data,
            qrScannedTime: latest.timestamp,
          }));
        }

        // QR history → update qrHistory state
        const histRes = await fetch("http://localhost:8000/api/qr-history");
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
        const latestRes = await fetch("http://localhost:8000/api/env/latest");
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

        const histRes = await fetch("http://localhost:8000/api/env/history");
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
