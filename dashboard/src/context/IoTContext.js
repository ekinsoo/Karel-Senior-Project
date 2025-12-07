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

  const value = {
    cameraData,
    sensorData,
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
