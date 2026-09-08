import {
  googleSignInAction,
  signInAction,
  signUpAction,
} from "@/app/auth/actions";
import styles from "./supabase-auth-form.module.css";

const errorCopy: Record<string, string> = {
  invalid_credentials: "That email and password combination was not accepted.",
  email_not_confirmed: "Confirm your email before signing in.",
  already_registered: "An account already exists for that email. Sign in instead.",
  weak_password: "Choose a stronger password with at least eight characters.",
  oauth_state: "The Google sign-in request could not be verified. Please try again.",
  oauth_exchange: "Google sign-in could not be completed. Please try again.",
  auth_not_configured: "Account access is not configured for this environment.",
  auth_error: "Account access could not be completed. Please try again.",
};

export function SupabaseAuthForm({
  mode,
  error,
  checkEmail,
}: {
  mode: "sign-in" | "sign-up";
  error?: string;
  checkEmail?: boolean;
}) {
  const isSignUp = mode === "sign-up";
  const action = isSignUp ? signUpAction : signInAction;

  return (
    <div className={styles.form}>
      {checkEmail ? (
        <div className={styles.notice} role="status">
          Check your inbox to confirm your email, then return here to sign in.
        </div>
      ) : null}
      {error ? (
        <div className={styles.error} role="alert">
          {errorCopy[error] ?? errorCopy.auth_error}
        </div>
      ) : null}

      <form className={styles.form} action={action}>
        <div className={styles.field}>
          <label htmlFor={mode + "-email"}>Email address</label>
          <input
            id={mode + "-email"}
            name="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor={mode + "-password"}>Password</label>
          <input
            id={mode + "-password"}
            name="password"
            type="password"
            autoComplete={isSignUp ? "new-password" : "current-password"}
            minLength={8}
            required
          />
        </div>
        <button className={styles.primary} type="submit">
          {isSignUp ? "Create candidate workspace" : "Sign in"}
        </button>
      </form>

      <div className={styles.divider}>or</div>

      <form action={googleSignInAction}>
        <button className={styles.oauth} type="submit">
          Continue with Google
        </button>
      </form>

      <p className={styles.help}>
        Your authentication session is verified by Supabase before ApplyAI forwards
        any candidate request to the API.
      </p>
    </div>
  );
}
