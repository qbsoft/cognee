import handleServerErrors from "./handleServerErrors";
import isCloudEnvironment from "./isCloudEnvironment";

let numberOfRetries = 0;

const isAuth0Enabled = process.env.USE_AUTH0_AUTHORIZATION?.toLowerCase() === "true";

// Temporarily use direct backend URL in development to avoid proxy issues
// TODO: Fix Next.js proxy configuration for POST requests
const isDevelopment = process.env.NODE_ENV === 'development';
const backendApiUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || "http://localhost:8000";

const cloudApiUrl = process.env.NEXT_PUBLIC_CLOUD_API_URL || "http://localhost:8001";

const mcpApiUrl = process.env.NEXT_PUBLIC_MCP_API_URL || "http://localhost:8001";

let apiKey: string | null = process.env.NEXT_PUBLIC_COGWIT_API_KEY || null;
let accessToken: string | null = null;

export default async function fetch(url: string, options: RequestInit = {}, useCloud = false): Promise<Response> {
  function retry(lastError: Response) {
    if (!isAuth0Enabled) {
      return Promise.reject(lastError);
    }

    if (numberOfRetries >= 1) {
      return Promise.reject(lastError);
    }

    numberOfRetries += 1;

    return global.fetch("/auth/token")
      .then(() => {
        return fetch(url, options);
      });
  }

  const authHeaders = useCloud && (!isCloudEnvironment() || !accessToken) ? {
    "X-Api-Key": apiKey,
  } : {
    "Authorization": `Bearer ${accessToken}`,
  }

  // Use Next.js proxy in development, direct URL only for cloud requests
  const fullUrl = useCloud 
    ? cloudApiUrl + "/api" + url.replace("/v1", "")
    : "/api" + url;  // Use relative path to go through Next.js proxy
  
  return global.fetch(
    fullUrl,
    {
      ...options,
      headers: {
        ...options.headers,
        ...authHeaders,
      } as HeadersInit,
      credentials: "include", // Always include credentials for cookies
    },
  )
    .then((response) => handleServerErrors(response, retry, useCloud))
    .catch((error) => {
      // Handle network errors more gracefully
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        console.error('[Fetch Error] Network error:', error);
        return Promise.reject(
          new Error("Backend server is not responding. Please check if the server is running.")
        );
      }
      
      // Log detailed error information
      const errorUrl = useCloud 
        ? cloudApiUrl + "/api" + url.replace("/v1", "")
        : `/api${url}`;  // Show proxy path
      console.error('[Fetch Error] Request failed:', {
        url: errorUrl,
        error,
        hasDetail: error.detail !== undefined,
        errorType: typeof error,
      });
      
      if (error.detail === undefined) {
        return Promise.reject(
          new Error(`No connection to the server. Error: ${error.message || JSON.stringify(error)}`)
        );
      }

      return Promise.reject(error);
    })
    .finally(() => {
      numberOfRetries = 0;
    });
}

fetch.checkHealth = async () => {
  const maxRetries = 5;
  const retryDelay = 1000; // 1 second
  
  // In development, use Next.js proxy; in production, use full URL
  const healthUrl = isDevelopment 
    ? "/health"  // Use Next.js proxy
    : `${backendApiUrl.replace("/api", "")}/health`;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await global.fetch(healthUrl);
      if (response.ok) {
        return response;
      }
    } catch (error) {
      // If this is the last retry, throw the error
      if (i === maxRetries - 1) {
        throw error;
      }
      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, retryDelay));
    }
  }
  
  throw new Error("Backend server is not responding after multiple attempts");
};

fetch.checkMCPHealth = () => {
  // In development, MCP server may not be running, so skip the check
  // to avoid connection refused errors in the console
  if (isDevelopment) {
    // Return a rejected promise that will be caught by the caller
    return Promise.reject(new Error("MCP server check skipped in development"));
  }
  
  // In production, try to connect to MCP server
  return global.fetch(`${mcpApiUrl.replace("/api", "")}/health`);
};

fetch.setApiKey = (newApiKey: string) => {
  apiKey = newApiKey;
};

fetch.setAccessToken = (newAccessToken: string) => {
  accessToken = newAccessToken;
};
