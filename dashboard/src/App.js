import { useState, useEffect } from "react";
import "bootstrap/dist/css/bootstrap.min.css";
import "./App.css";
import Dashboard from "./components/Dashboard";
import { IoTDataProvider } from "./context/IoTContext";

function App() {
  return (
    <IoTDataProvider>
      <Dashboard />
    </IoTDataProvider>
  );
}

export default App;
