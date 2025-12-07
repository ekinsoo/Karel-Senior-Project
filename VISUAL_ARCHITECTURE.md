# Visual Architecture

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        KAREL PRODUCTION LINE                    │
│                   PCB Defect Detection System                    │
└─────────────────────────────────────────────────────────────────┘

┌────────────────────┐         ┌────────────────────┐
│   JETSON NANO      │         │    ESP32 BOARD     │
│  + AI Inference    │         │  + Sensor Network  │
│  + Camera Module   │         │                    │
│  (IMX219-160)      │         │ • Temperature      │
│                    │         │ • Humidity         │
│ • PCB Inspection   │         │ • QR Scanner       │
│ • Defect Detection │         │                    │
│ • ML Model         │         │                    │
└─────────┬──────────┘         └────────┬───────────┘
          │ MQTT                        │ MQTT
          │                             │
          └──────────────┬──────────────┘
                         │
                    MQTT Broker
                  (Mosquitto:1883)
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          │              │              │
   ┌──────▼──────┐      │       ┌──────▼──────┐
   │  FastAPI    │      │       │   Redis     │
   │  Server     │      │       │   (Cache)   │
   │  :8000      │      │       └─────────────┘
   │             │      │
   │ • MQTT Sub  │      │
   │ • Image Srv │      │
   │ • API Gate  │      │
   └──────┬──────┘      │
          │             │
          │ HTTP/REST   │
          └──────┬──────┴──────┐
                 │             │
                 │             │
          ┌──────▼──────────────▼──────┐
          │                             │
          │   REACT DASHBOARD :3000     │
          │   ┌────────────────────┐    │
          │   │     HEADER         │    │
          │   │  Status & Uptime   │    │
          │   ├────────────────────┤    │
          │   │   CAMERA FEED      │    │
          │   │  + Defect Overlay  │    │
          │   ├────────────────────┤    │
          │   │  SENSOR PANEL      │    │
          │   │  DEFECT STATUS     │    │
          │   │  STATISTICS        │    │
          │   │  SYSTEM STATUS     │    │
          │   │  ALERT PANEL       │    │
          │   └────────────────────┘    │
          │                             │
          └─────────────────────────────┘
                 ↓
          USER BROWSER
        (Your Screen :3000)
```

## Component Hierarchy

```
App (IoTDataProvider wrapper)
│
└─ Dashboard (Main Layout)
   ├─ Header
   │  ├─ System Health Badge
   │  ├─ Device Icons (4x)
   │  └─ Uptime Counter
   │
   ├─ Main Content Grid
   │  ├─ Row 1: Camera + Alerts
   │  │  ├─ CameraFeed (8 cols)
   │  │  │  ├─ Live Stream
   │  │  │  ├─ Defect Overlay
   │  │  │  └─ Frame Info
   │  │  │
   │  │  └─ AlertPanel (4 cols)
   │  │     ├─ Alert Count Badge
   │  │     └─ Alert Items (max 5)
   │  │
   │  ├─ Row 2: Metrics Grid (4 columns)
   │  │  ├─ SensorMonitoring
   │  │  │  ├─ Temperature
   │  │  │  ├─ Humidity
   │  │  │  └─ QR Code
   │  │  │
   │  │  ├─ DefectDetection
   │  │  │  ├─ Status Circle
   │  │  │  ├─ Confidence Bar
   │  │  │  └─ Defect Counter
   │  │  │
   │  │  ├─ Statistics
   │  │  │  ├─ Total Inspected
   │  │  │  ├─ Defects Found
   │  │  │  ├─ Defect Rate
   │  │  │  └─ Avg Process Time
   │  │  │
   │  │  └─ SystemStatus
   │  │     ├─ Jetson Status
   │  │     ├─ ESP32 Status
   │  │     ├─ Camera Status
   │  │     ├─ MQTT Status
   │  │     ├─ Model Status
   │  │     └─ Uptime Display
   │  │
   │  └─ Row 3: Stats Detail Grid (5 columns)
   │     ├─ Total Inspected Card
   │     ├─ Defects Found Card
   │     ├─ Defect Rate Card
   │     ├─ Avg Time Card
   │     └─ Today's Defects Card
   │
   └─ Footer
      └─ Copyright & Info
```

## Data Flow Diagram

```
┌─────────────────┐
│  Jetson Camera  │
│   (JPEG Frames) │
└────────┬────────┘
         │
    MQTT Topic:
  jetson/camera/
    image/jpeg
         │
    ┌────▼─────────────────┐
    │  FastAPI Server      │
    │  MQTT Subscriber     │
    ├────────────────────┬─┘
    │ Receives: Image    │
    │ Saves: latest.jpg  │
    │ Process Requests   │
    └────────┬───────────┘
             │
         HTTP GET
       /api/latest-image
      (with cache buster)
             │
        ┌────▼──────────────────┐
        │  React IoT Context    │
        │  IoTDataProvider      │
        ├────────────────────┬──┘
        │ Updates every 2s   │
        │ Stores: cameraData │
        │ Subscribes: All    │
        └────────┬───────────┘
                 │
          ┌──────▼────────┬────────────┬──────────┐
          │               │            │          │
    ┌─────▼────┐ ┌────────▼──┐ ┌──────▼──┐ ┌────▼──────┐
    │  Camera  │ │  Sensor  │ │ Defect  │ │Statistics│
    │  Feed    │ │ Monitor  │ │ Status  │ │ & Status │
    │Component │ │Component │ │ Comp.   │ │Components│
    └──────────┘ └──────────┘ └─────────┘ └──────────┘
         │              │            │           │
         └──────────────┴────────────┴───────────┘
                       │
                 ┌─────▼──────┐
                 │  Dashboard │
                 │  Layout    │
                 └─────┬──────┘
                       │
                 ┌─────▼──────────┐
                 │  User Browser  │
                 │ Visual Display │
                 └────────────────┘
```

## Real-Time Update Cycle

```
Every 2 Seconds:
├─ Camera Feed Update
│  ├─ Fetch /api/latest-image
│  ├─ Update imageSrc
│  └─ Increment frameCount
│
├─ Temperature Update
│  ├─ Simulate ±1°C variation
│  ├─ Determine Status
│  │  ├─ < 28°C → Normal (Green)
│  │  ├─ 28-30°C → Warning (Orange)
│  │  └─ > 30°C → Critical (Red)
│  └─ Update Display
│
├─ Humidity Update
│  ├─ Simulate ±0.5% variation
│  └─ Update Progress Bar
│
├─ Timestamp Updates
│  ├─ Refresh timestamp badge
│  └─ Update last update time
│
├─ Defect Check (5% probability)
│  ├─ Generate random defect
│  ├─ Select defect type
│  │  ├─ Solder Joint
│  │  ├─ Copper Trace
│  │  └─ Missing Component
│  ├─ Set confidence (0-100%)
│  ├─ Create alert
│  └─ Update counter
│
└─ Every 10 cycles (20 seconds):
   ├─ Update Statistics
   │  ├─ Increment total
   │  ├─ Add new defects
   │  └─ Recalculate rate
   │
   └─ Update System Status
      └─ Refresh all device status
```

## Temperature Status Logic

```
Temperature Range Chart:
┌─────────────────────────────────────────┐
│  Optimal: 22-26°C  [GREEN]              │
├─────────────────────────────────────────┤
│  Acceptable: 18-22°C, 26-28°C [GREEN]   │
├─────────────────────────────────────────┤
│  Warning: 28-30°C [ORANGE]              │
├─────────────────────────────────────────┤
│  Critical: > 30°C [RED]                 │
├─────────────────────────────────────────┤
│  Low: < 18°C [BLUE]                     │
└─────────────────────────────────────────┘

Color Indicators:
🟢 Green  (18-28°C)  : NORMAL - Optimal range
🟠 Orange (28-30°C)  : WARNING - Above optimal
🔴 Red    (>30°C)    : CRITICAL - Action required
```

## Defect Detection Logic

```
Defect Status Display:
┌──────────────────────────────────────┐
│     Confidence: 95%                  │
│     ███████████████░░ 95%            │
├──────────────────────────────────────┤
│  Status Colors:                      │
│  • 0-50%:   YELLOW  (Investigation)  │
│  • 51-79%:  ORANGE  (Monitor)        │
│  • 80-100%: RED     (Alert)          │
└──────────────────────────────────────┘

Defect Type Classification:
├─ Solder Joint
│  └─ Dry joints, cold joints, insufficient solder
├─ Copper Trace
│  └─ Breaks, shorts, corrosion
└─ Component Missing
   └─ Wrong placement, not placed, shifted
```

## Alert System Flow

```
Defect Detected
    ├─ Create Alert Object
    │  ├─ id: timestamp
    │  ├─ type: "defect"
    │  ├─ message: defect description
    │  ├─ severity: "high"
    │  └─ timestamp: current time
    │
    ├─ Add to AlertPanel
    │  └─ Max 5 alerts shown
    │
    ├─ Display Overlay
    │  ├─ Slide down animation
    │  ├─ Red border flash
    │  └─ Pulsing indicator
    │
    └─ Log Statistics
       ├─ Increment defect count
       ├─ Update defect rate
       └─ Store timestamp
```

## Responsive Layout Breakpoints

```
Desktop (≥1920px)
┌────────────────────────────────────┐
│         HEADER (Full Width)         │
├─────────────────────┬───────────────┤
│   CAMERA FEED       │    ALERTS     │
│   (8 cols)          │   (4 cols)    │
├─────┬─────┬─────┬───┤
│SEN  │DEF  │STAT │SYS│
│(3c) │(3c) │(3c) │(3c)
├────────────────────────────────────┤
│   STATS DETAIL GRID (5 cards)      │
├────────────────────────────────────┤
│         FOOTER (Full Width)         │
└────────────────────────────────────┘

Tablet (768-1919px)
┌────────────────────────────────────┐
│    HEADER (Adjusted)                │
├─────────────────────────────────────┤
│   CAMERA FEED      │    ALERTS      │
│   (Full/2)         │   (Full/2)     │
├────────────┬────────────────────────┤
│ SEN │ DEF  │ STAT │ SYS │
├────────────────────────────────────┤
│   STATS DETAIL GRID (responsive)   │
└────────────────────────────────────┘

Mobile (<768px)
┌────────────────────────────┐
│   HEADER (Stacked)         │
├────────────────────────────┤
│   CAMERA FEED (Full)       │
├────────────────────────────┤
│   ALERTS (Full)            │
├────────────────────────────┤
│   SENSORS (Full)           │
├────────────────────────────┤
│   DEFECTS (Full)           │
├────────────────────────────┤
│   STATS (Full)             │
├────────────────────────────┤
│   SYSTEM STATUS (Full)     │
├────────────────────────────┤
│   STATS DETAIL (Full)      │
├────────────────────────────┤
│   FOOTER (Full)            │
└────────────────────────────┘
```

## Color Palette

```
BLUES & PURPLES:
├─ Primary BG:   #0a0e27  (Dark Navy)
├─ Secondary BG: #151b3b  (Medium Navy)
├─ Tertiary BG:  #1e2849  (Card Background)
├─ Border:       #2d3854  (Subtle Border)
└─ Info:         #00aaff  (Neon Blue)

GREENS (Success):
├─ Primary:      #00ff00  (Neon Green)
├─ Hover:        #00dd00  (Slightly Darker)
└─ Gradient:     Linear (Green → Green)

REDS (Danger):
├─ Primary:      #ff3333  (Neon Red)
├─ Dark:         #dd0000  (Darker Red)
└─ Gradient:     Linear (Red → Dark Red)

ORANGES (Warning):
├─ Primary:      #ffaa00  (Neon Orange)
├─ Dark:         #ff8800  (Darker Orange)
└─ Gradient:     Linear (Orange → Dark Orange)

TEXT:
├─ Primary:      #ffffff (Pure White)
└─ Secondary:    #b0b8d4 (Light Gray)
```

## Animation Specifications

```
Float (Logo):
├─ Duration: 3s
├─ Easing: ease-in-out
├─ Transform: translateY(0 → -10px → 0)
└─ Effect: Floating animation

Pulse (Status Dots):
├─ Duration: 2s
├─ Iteration: infinite
├─ Opacity: 1 → 0 → 1
└─ Effect: Pulsing glow

Blink (Live Indicator):
├─ Duration: 1.5s
├─ Iteration: infinite
├─ Opacity: 1 → 0.3 → 1
└─ Effect: Blinking dot

ExpandPulse (Defect Ring):
├─ Duration: 2s
├─ Iteration: infinite
├─ Transform: scale(1 → 1.4)
├─ Opacity: 1 → 0
└─ Effect: Expanding ring

SlideDown (Defect Overlay):
├─ Duration: 0.5s
├─ Transform: translateY(-20px → 0)
├─ Opacity: 0 → 1
└─ Effect: Slide down appearance
```

---

**Visual Guide Version**: 1.0  
**Created**: November 2024
