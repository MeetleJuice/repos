# Idea Foundry 0.7.2 — Windows verification workspace cleanup

The user's Windows/Python 3.13 run passed health, page, script and stylesheet checks, then
failed deleting its disposable acceptance directory with WinError 32. The verifier was still
inside that directory. Linux permits unlinking the current directory, so the earlier Linux
runs did not reveal this bug. The failure was then mistaken for an app/asset error, wasting
model repair requests. Those repairs could not fix the verifier's working directory.

## Recover the existing project

1. Update → Check for updates → Install & restart. Keep the terminal open.
2. Reopen the existing Neon Dodge project; no new proposal or generation is needed.
3. Keep your explicitly chosen runtime. Set Maximum repairs to **0** for this diagnostic retry.
4. Approve execution if prompted and click Build, test & repair.
5. After automated checks pass, download and launch the app and complete its manual gameplay checks.

Existing files, accepted requirements, checkpoints and manual check definitions are preserved.
The update does not reset repair history or claim that previous failed runs succeeded.

## Fix and failure handling

Every acceptance/tests/launch phase now saves its original cwd and import path, restores them
in finally, and only then removes its disposable workspace. Restoration also occurs when app
code raises or generated tests change cwd/import paths. Cleanup exceptions are not ignored.

Workspace creation, staging or cleanup errors emit structured environment failures across both
process boundaries. The local runner preserves that category, and the core stops before any
application repair request. Actual app assertion failures retain their application category.
Passed asset log lines no longer cause an unrelated error to be labeled a missing asset.

Tests enforce the Windows current-directory deletion rule on Linux and exercise restoration on
success/failure, generated cwd changes, cleanup errors, structured process reports and zero
repair requests for environment failures. CI adds Python 3.13 to both Windows and Linux jobs.
Actual Windows execution remains to be confirmed on the user's machine/hosted CI; simulated
Windows cleanup behavior is distinguished from a native Windows run in VALIDATION.md.
