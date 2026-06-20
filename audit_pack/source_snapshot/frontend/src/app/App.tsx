import "../styles/global.css";

import { RouteRegistry } from "../router/RouteRegistry";

export default function App() {
  return (
    <div className="app-root">
      <RouteRegistry />
    </div>
  );
}
