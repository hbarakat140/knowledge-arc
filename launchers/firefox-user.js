// Settings for the drive's own Firefox, copied into a fresh, temporary
// profile each time the full library opens (launchers/open-knowledge-arc.*).
// Offline use: no first-run pages, no update or telemetry attempts, no
// default-browser question.
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.aboutwelcome.enabled", false);
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("app.update.auto", false);
user_pref("browser.tabs.warnOnClose", false);
user_pref("extensions.update.enabled", false);
user_pref("browser.search.update", false);
