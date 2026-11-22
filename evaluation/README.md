# Warehouse OS instructor evaluation

## Instructor walkthrough

1. Open the complete invitation privately in a fresh browser window. It takes you to the original dashboard. The invitation can be used once within one hour. The resulting browser session lasts up to one hour.
2. Open **Inventory**, enter a unique SKU and product name, and select **Add product**. Select that SKU and **Evaluation Center**, add the stock location, then record a receipt of five units. Verify the on-hand and available quantities.
3. Open **Agents** and choose **Run Evaluation Workflow** once. It creates its own SKU and order, receives five units, reserves two, routes the order, books a sandbox shipment and dispatches it. Signed tracking events and a Celery monitoring cycle exercise delay prediction, rerouting evaluation, cost analysis and sandbox communication. The run records delivery.
4. Refresh the page during the run to resume watching. After completion, open the run details, use **Refresh agent status**, and expand each card. Match execution IDs, times and results to the completed run. An idle card with a completed event is the expected final state.
5. Check the delivered order under **Orders**. Open **Chat**, enter “List orders”, and refresh to check the conversation history. The default workspace uses the application's fallback. Live Gemini requires a separately approved evaluation key and model on the owner machine.
6. Close the evaluation window when finished. Ask the owner for a fresh invitation if it was already used, expired or revoked.

## Owner controls on the existing Windows fixture

From the repository root in PowerShell, with the isolated fixture PostgreSQL service listening on loopback port 55471 and the instructor frontend already built:

```powershell
$python = '.\order-fulfillment-coordinator\apps\api\.venv\Scripts\python.exe'
& $python evaluation/workspace.py
```

Keep that terminal open. In another owner terminal from the repository root, issue the invitation. Share the entire link privately. Running the command again invalidates the previous invitation and session.

```powershell
& .\order-fulfillment-coordinator\apps\api\.venv\Scripts\python.exe evaluation/workspace.py invite
```

Use the same command with **revoke** to deny subsequent requests immediately. A workflow already accepted can finish. Each workspace launch creates a fresh database and separate login. Only the local owner can issue invitations. Run the automated walkthrough with `.\.tools\node-v24.22.2-win-x64\node.exe evaluation/browser-test.cjs` before inviting the instructor, since the walkthrough issues and revokes its own invitation.

To rebuild the dedicated UI, use the existing Node runtime and installed npm dependencies in the frontend directory. Set `NEXT_PUBLIC_INSTRUCTOR_WORKSPACE=1` and `BACKEND_URL=http://127.0.0.1:8386`, then run `node node_modules/next/dist/bin/next build --webpack`. The build uses its own output directory.

## Proposed remote session requiring owner approval

Stop the **instructor workspace only** before publishing. After explicit approval, run `cloudflared tunnel --url http://127.0.0.1:8387` with the existing cloudflared client. Set `EVALUATION_ORIGIN` to the exact issued HTTPS origin in both workspace and invitation/test terminals. Start the instructor workspace, then run the fresh-browser acceptance test through that hostname. After it passes, issue a new private invitation for the instructor. The bare hostname grants no warehouse access.

Keep the host awake and the tunnel and workspace running. Revoke the session and stop cloudflared to withdraw access. This temporary Quick Tunnel requires outbound Cloudflare connectivity and has no uptime guarantee. It forwards only the invitation gateway. PostgreSQL, the broker, the frontend and the API use loopback listeners.
