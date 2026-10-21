# Idea Foundry 0.33.1

The published release includes all [scope-first planning and Test → Diag features](RELEASE-0.33.0.md), plus a startup interruption cleanup fix discovered while validating the unpromoted 0.33.0 candidate.

One extracted full-suite run left an instance marker after console shutdown. The focused check and twelve standalone repetitions passed, so that occurrence's exact signal timing was not established. A separate deterministic regression reproduced the same invariant failure by interrupting after instance publication but before serving. Cleanup now also runs at the outer shutdown boundary, suppresses further console interrupts during cleanup, removes only the marker owned by its nonce, and closes a startup-allocated server. Existing ownership safeguards remain.

The failed candidate ZIP was quarantined locally rather than published. The shipped version is **0.33.1**. Use **Update → Check for updates → Install & restart**. Then select your project, open **Test**, run the desired checks, and collect **Diag** after they finish. Cloud response probes require separate consent and may incur charges.

See the versioned validation record for exact source/extracted test results. Live providers, physical Windows GPU performance and remaining account credits are not proved by fixture tests.

```text
python -m unittest discover -q
Ran 520 tests in 134.841s
OK
```

Strict checks passed on 36 Python modules. Test → Diag, proof planning and builder-capacity browser flows were rechecked after the cleanup fix; the complete 23-script workbench browser set and Dashboard checks had already passed before that isolated lifecycle change. The release artifact records extracted-copy checks separately.
