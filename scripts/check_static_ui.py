# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
#!/usr/bin/env python3
"""Verify nordctl static UI wiring — HTML ids, JS hooks, CSS classes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "nordctl" / "static"

REQUIRED_HTML_IDS = [
    "overallAuditPanel", "overallAuditBadge", "overallAuditCategories", "btnRunOverallAudit",
    "auditToolsBox", "auditToolsList", "auditEmailBox", "auditEmailWhenDone", "btnAuditEmailSend",
    "btnAuditEmailSetup", "auditSubnav", "auditLeakPanel", "myPresetSuggestions", "connJournal",
    "settingsDisconnectWatch", "trafficHubSubnav", "trafficOutboundBody", "trafficLocalSessions",
    "viewAdvanced", "btnTrafficRefresh", "btnTrafficLocalRefresh", "viewLogs", "logsList",
    "btnLogsRefresh", "viewTerminal", "termViewport", "termPostInstallBar", "termInput",
    "termScreen", "termSessionTabs", "btnTermCloseTab", "termSudoPrompt", "btnTermSudoSend",
    "btnTermConnect", "helpFullNav", "viewSecurity", "secHealthScore", "viewWifi",
    "wifiProfileTable", "wifiProfileSummary", "btnWifiHeal", "wifiDnsStatus", "connectScenarioGrid",
    "connectLocationProfiles", "viewDoctors", "doctorsHubSubnav", "networkHubSubnav", "dashSubnav",
    "hubNavWrap", "tabLoadingOverlay", "pageIntroBar", "pageIntroHelpBtn", "onboardOverlay",
    "btnOnboardContinue", "nordExtrasPanel", "btnEnableNetworkHub", "btnSwitchVpnMode",
    "toolsWelcomePanel", "toolsWelcomeGrid", "usageModeBadge", "hubSubnav", "toolsSubnav",
    "automateGuideGrid", "automateGuideBadge", "automateGuideLead", "automateWatcherFallback",
    "automateSchedulesFallback", "automateSnapshotsFallback", "btnAlertBell", "bellDropdown",
    "settingsPanel", "settingsScopeNav", "settingsSubnav", "settingsTitle", "settingsIntro",
    "settingsNotifyRules", "settingsNotifyBadge", "settingsWatchStats", "settingsEmailTo",
    "settingsSmtpHost", "btnSettingsEmailSave", "btnSettingsNotifySave", "btnSettingsNotifyTest",
    "uiLoginOverlay", "workflowsHub", "createPresetsHub", "presetBuilderHow", "myPresetsGrid",
    "myPresetsCount", "myPresetsHiddenPanel", "btnOpenPresetBuilder", "presetBuilderOverlay",
    "presetBuilderForm", "presetBuilderResults", "presetBuilderCompatIntro",
    "presetBuilderSavedBanner", "pbExtrasGrid", "pbMeshPeerRow", "switchesPanel",
    "switchesConnBadge", "switchesConnSummary", "workflowsHow", "locationSettingsGrid",
    "btnAddPreset", "btnAddPresetExample", "noticeSetup", "ufwEditorPanel", "wifiHubSubnav",
    "networkToolsGrid", "secToolsGrid", "btnUfwAdd", "btnFactoryReset", "factoryResetBox",
    "quickStartCards", "networkAccessPanel", "networkAccessBox", "netAccessBadge",
    "btnPrivRefresh", "doctorReportPanel", "doctorReportSummary", "setupNordDoctor",
    "nordDocBadge", "nordDocSummary", "nordDocChecks", "btnNordDocRefresh", "netDocBadge",
    "netDocChecks", "diagnosticsSubnav", "diagnosticsChecksPanel", "diagnosticsShellPanel",
]


def main() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    for eid in REQUIRED_HTML_IDS:
        assert f'id="{eid}"' in html, eid

    assert html.index('id="termViewport"') < html.index('id="termPostInstallBar"'), (
        "post-install bar should sit below terminal output"
    )

    assert "loadTraffic" in js and "renderTrafficMap" in js and "switchTrafficHubTab" in js
    assert "TRAFFIC_HUB_TABS" in js
    assert "loadSecurity" in js and "renderSecurityHub" in js and "loadScenarios" in js
    assert "renderLocationScenarios" in js and "renderWorkflowPresets" in js
    assert "loadConnectExtras" in js and "renderConnectScenarios" in js
    assert "network/doctors/nordvpn" in js and "dashboard/nord-doctor" in js
    assert 'data-view="tools"' in html
    assert "diagnosticsShellScopeNav" in html
    assert "renderAutomateGuide" in js and "isToolsHubActive" in js
    assert "TOOLS_NORD_ONLY_TABS" in js and "renderAutomateNordGates" in js
    assert "loadWifiHub" in js and "renderWifiHub" in js
    assert "loadUfw" in js and "initGlobalConfirm" in js and "renderMeshPeers" in js
    assert "initViewRouting" in js
    assert not (STATIC / "i18n.js").is_file(), "i18n removed"
    assert "showNordFeatures" in js and "applyNordUiVisibility" in js and "loadNordDoctor" in js
    for token in (
        "loadHubTools", "renderHubToolCards", "renderAllHubToolCards", "PACKAGE_HUB_TABS",
        "loadCustomPackages", "switchWifiHubTab", "switchDoctorsHubTab", "switchNetworkHubTab",
        "switchTrafficHubTab", "switchAuditPane", "switchDiagnosticsPane", "LEGACY_HUB_TABS",
        "loadPresetSuggestions", "loadConnJournal", "WIFI_HUB_TABS", "DOCTORS_HUB_TABS",
        "NETWORK_HUB_TABS", "HUB_PRIMARY_TABS", "switchHubPrimaryTab", "initHubPrimarySubnav",
        "refreshAfterToolInstall",
    ):
        assert token in js, token
    assert "setup:" in js and "network/audit/leak" in js and "network/diagnostics/packages" in js
    assert 'diagnostics: { redirectTab: "networking-shell"' in js
    assert 'setup: { redirectTab: "security-packages"' in js
    assert js.index("const NETWORK_LEGACY_SUB") < js.index("if (NETWORK_LEGACY_SUB[networkHubTab])")
    for token in (
        "renderMyPresets", "renderCreatePresetsList", "renderPresetBuilderExtrasGrid",
        "applyPresetBuilderHelp", '"create-presets"', "loadTerminal", "termConnect", "termRunCommand",
        "termOpenSession", "termSyncSessions", "termSwitchTab", "termInput", "termSubmitSudoPassword",
        "termShowSudoPrompt", "termSyncSudoPrompt", "AUDIT_RETURN_ROUTE",
        "termRehydratePackageInstallContext", "scrollToPostInstallBar", "NETWORK_SETUP_TOOLS",
        "initEditorView", "loadFileList", "categorySlug", "runLeakLab", "renderLabResults",
        "loadOverallAudit", "renderOverallAudit", "renderAuditTools", "sendAuditEmailReport",
        "loadDoctorReport", "loadPrivileges", "viewLink", "renderNetworkAccess", "isToolsOnly",
        "showMissingFieldWizard", "renderLocationSettings", "placeValueLabel", "scrollToPlaceField",
        "switchHubTab", "switchToolsTab", "switchPageTabs", "renderPresets",
        "renderDashboardPresetPanels", "DASHBOARD_PRESET_PANELS", "parseRouteHash", "navigateRoute",
        "resolveViewJump", "showTabLoading", "renderFlatTabNav", "DASHBOARD_TABS", "TAB_INTROS",
        "syncPageIntro", "syncDashTabHighlight", "refreshAll", "loadSettingsPanel",
        "SETTINGS_TAB_META", "SETTINGS_SCOPE_META", "applySettingsNav", "switchSettingsTab",
        "initSettingsSubnav", "switchToVpnMode", "UI_TOKEN_KEY",
    ):
        assert token in js, token
    assert "Whole hub tab ids with dashes" in js
    assert js.index("HUB_TABS[parts[1]]") < js.index("Compound hub routes")
    assert "nettoolButtons" not in html, "lab nettools should be removed"

    assert css.count("{") == css.count("}"), "app.css brace mismatch"
    assert ".preset-builder-overlay {" in css and ".preset-breakdown-card {" in css
    for cls in (
        "page-metrics", "page-metric", "page-hero", "page-section-head", "page-empty",
        "topbar-stack", "live-bw-metrics", "speed-lab-page",
    ):
        assert f".{cls}" in css, f"missing CSS for .{cls}"
    assert 'class="page-metrics' in html, "index.html uses page-metrics"

    from nordctl.static_assets import verify_static_ui

    ui = verify_static_ui()
    assert ui["ok"], f"UI static assets incomplete: {ui.get('missing_css')}"
    print("HTML/JS element checks")


if __name__ == "__main__":
    main()
