/** Build the write contract explicitly, even when an older server returns KV metadata.
 * @param {import('./types').Settings} settings
 * @param {string} token
 */
export function connectionSettingsPayload(settings, token = "") {
  return {
    soar_url: settings.soar_url,
    instance_name: settings.instance_name,
    asset_id: settings.asset_id,
    ca_pem: settings.ca_pem,
    ignore_certificate_errors: settings.ignore_certificate_errors ?? false,
    request_timeout: settings.request_timeout,
    label_prefix: settings.label_prefix ?? "",
    revision: settings.revision,
    ...(token ? { token } : {}),
  };
}
