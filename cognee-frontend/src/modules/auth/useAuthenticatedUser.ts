import { useEffect, useState } from "react";
import { fetch } from "@/utils";
import { User } from "./types";

export default function useAuthenticatedUser() {
  const [user, setUser] = useState<User>();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!user) {
      setIsLoading(true);
      fetch("/v1/auth/me")
        .then((response) => response.json())
        .then((data) => {
          setUser(data);
          setError(null);
        })
        .catch((err) => {
          // Don't set error if it's a 401 (user will be redirected)
          if (err.status !== 401) {
            setError(err);
          }
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, [user]);

  return { user, isLoading, error };
}
