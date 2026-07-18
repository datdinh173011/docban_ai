import { useCallback, useEffect, useState } from "react";

export type Route = "app" | "privacy";

export function getRoute(): Route {
  return window.location.pathname === "/privacy" ? "privacy" : "app";
}

export function navigate(route: Route) {
  const path = route === "privacy" ? "/privacy" : "/";
  if (window.location.pathname !== path) window.history.pushState({}, "", path);
}

export function useRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = useState<Route>(() => getRoute());

  useEffect(() => {
    function onPopState() {
      setRoute(getRoute());
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const go = useCallback((nextRoute: Route) => {
    navigate(nextRoute);
    setRoute(nextRoute);
  }, []);

  return [route, go];
}
