"use client";

import React, { useState, useEffect, useCallback } from "react";
import Navbar, { ActiveTab } from "@/components/Navbar";
import UnifiedChatView from "@/components/UnifiedChatView";
import DocumentIngestView from "@/components/DocumentIngestView";
import TelemetryBar from "@/components/TelemetryBar";
import AuthModal from "@/components/AuthModal";
import { api, HealthStatus, DecodedToken } from "@/lib/api";

export default function Home() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("chat");
  const [health, setHealth] = useState<HealthStatus>({ status: "checking" });
  const [lastTraceId, setLastTraceId] = useState<string>("Standby");
  const [lastLatencyMs, setLastLatencyMs] = useState<number>(0);
  const [queryCount, setQueryCount] = useState<number>(0);

  // Auth modal & session state
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [decodedUser, setDecodedUser] = useState<DecodedToken | null>(null);

  // Refresh auth state from storage & API client
  const refreshAuthState = useCallback(() => {
    const token = api.getToken();
    setIsAuthenticated(!!token);
    setDecodedUser(api.getDecodedUser());
  }, []);

  // 1. Initial health ping and session check
  useEffect(() => {
    let isMounted = true;

    const checkSystemHealth = async () => {
      try {
        const h = await api.checkHealth();
        if (isMounted) setHealth(h);
      } catch {
        if (isMounted) setHealth({ status: "disconnected" });
      }
    };

    checkSystemHealth();
    const interval = setInterval(checkSystemHealth, 12000);

    // Check existing stored token (no auto-login)
    refreshAuthState();

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [refreshAuthState]);

  const handleLogout = () => {
    api.logout();
    refreshAuthState();
  };

  const handleTelemetryUpdate = (traceId: string, latencyMs: number) => {
    setLastTraceId(traceId);
    setLastLatencyMs(latencyMs);
    setQueryCount((prev) => prev + 1);
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top Glass Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
        onOpenAuth={() => setIsAuthModalOpen(true)}
        onLogout={handleLogout}
        isAuthenticated={isAuthenticated}
        currentUserEmail={decodedUser?.email}
        currentUserRole={decodedUser?.role}
        currentUserTenant={decodedUser?.tenant_id}
      />

      {/* Main Content Viewport with clearance for bottom telemetry bar */}
      <main className="aura-container" style={{ flex: 1, paddingTop: "8px", paddingBottom: "80px" }}>
        {activeTab === "chat" && (
          <UnifiedChatView onTelemetryUpdate={handleTelemetryUpdate} />
        )}
        {activeTab === "docs" && (
          <DocumentIngestView
            isAuthenticated={isAuthenticated}
            onOpenAuth={() => setIsAuthModalOpen(true)}
            currentUserRole={decodedUser?.role}
            currentUserTenant={decodedUser?.tenant_id}
          />
        )}
      </main>

      {/* Sticky Bottom Telemetry Status Bar with 100% Real Live Metrics */}
      <TelemetryBar
        lastTraceId={lastTraceId}
        lastLatencyMs={lastLatencyMs}
        totalQueriesRun={queryCount}
        authenticatedRole={decodedUser?.role}
        authenticatedTenant={decodedUser?.tenant_id}
        isAuthenticated={isAuthenticated}
      />

      {/* Single-User Authentication & Registration Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthChange={refreshAuthState}
      />
    </div>
  );
}
