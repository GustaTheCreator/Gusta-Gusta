import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { PipecatAppBase, type PipecatBaseChildProps } from "@pipecat-ai/voice-ui-kit";

import { Orb } from "./Orb";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PipecatAppBase
      transportType="smallwebrtc"
      connectParams={{ webrtcUrl: "/api/offer" }}
      noThemeProvider
    >
      {({ handleConnect, handleDisconnect, error }: PipecatBaseChildProps) => (
        <Orb onConnect={handleConnect} onDisconnect={handleDisconnect} error={error} />
      )}
    </PipecatAppBase>
  </StrictMode>,
);
