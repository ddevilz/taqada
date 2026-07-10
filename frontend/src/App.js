import "@/App.css";
import "@/index.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Dashboard from "@/pages/Dashboard";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#0A1128",
            color: "#F9F6F0",
            borderRadius: 0,
            border: "1px solid #0A1128",
            fontFamily: "IBM Plex Mono",
            fontSize: 12,
          },
        }}
      />
    </div>
  );
}

export default App;
