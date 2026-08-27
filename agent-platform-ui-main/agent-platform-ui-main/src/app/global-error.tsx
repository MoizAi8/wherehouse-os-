"use client";

import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Application Error — Warehouse OS</title>
        <style jsx>{`
          * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
          }
          html,
          body {
            height: 100%;
            font-family: var(--font-sora), system-ui, sans-serif;
          }
          body {
            display: flex;
            align-items: center;
            justify-content: center;
            background: #0a0a0f;
            color: #fafafa;
            min-height: 100vh;
          }
          .error-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 2rem;
            max-width: 480px;
            width: 100%;
          }
          .error-icon {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1.5rem;
            box-shadow: 0 0 40px rgba(239, 68, 68, 0.4);
          }
          .error-icon svg {
            width: 40px;
            height: 40px;
            color: white;
          }
          h1 {
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: #fafafa;
            letter-spacing: -0.02em;
          }
          .error-message {
            color: #a1a1aa;
            font-size: 1rem;
            margin-bottom: 2rem;
            line-height: 1.6;
          }
          .error-details {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 0.75rem;
            padding: 1rem;
            margin-bottom: 2rem;
            width: 100%;
            text-align: left;
            font-family: monospace;
            font-size: 0.8rem;
            color: #fca5a5;
            overflow-x: auto;
          }
          .reset-button {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            border: none;
            border-radius: 0.5rem;
            padding: 0.875rem 2rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
          }
          .reset-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(59, 130, 246, 0.4);
          }
          .reset-button:active {
            transform: translateY(0);
          }
          .reset-button:focus-visible {
            outline: 2px solid #3b82f6;
            outline-offset: 2px;
          }
        `}</style>
      </head>
      <body>
        <div className="error-container">
          <div className="error-icon" role="img" aria-label="Error">
            <svg fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
              />
            </svg>
          </div>
          <h1>Something went wrong</h1>
          <p className="error-message">
            An unexpected error occurred. Our agents have been notified and are investigating.
          </p>
          {error.digest && (
            <div className="error-details">
              Error ID: {error.digest}
            </div>
          )}
          <Button className="reset-button" onClick={reset}>
            Try again
          </Button>
        </div>
      </body>
    </html>
  );
}

