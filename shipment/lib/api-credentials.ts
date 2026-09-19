const env = (name: string) => {
  const value = process.env[name]?.trim();
  return value || undefined;
};

export function getApiCredentials() {
  const wbToken = env("WB_API_KEY");
  const ozonClientId = env("OZON_CLIENT_ID");
  const ozonApiKey = env("OZON_API_KEY");
  const moyskladToken = env("MOYSKLAD_TOKEN");

  return {
    wbToken,
    ozonClientId,
    ozonApiKey,
    moyskladToken,

    manual: {
      wbToken: Boolean(wbToken),
      ozonClientId: Boolean(ozonClientId),
      ozonApiKey: Boolean(ozonApiKey),
      moyskladToken: Boolean(moyskladToken),
    },
  };
}