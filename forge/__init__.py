"""Idea Foundry: a local idea-to-app workbench."""

__version__ = "0.28.1"

__release_notes__ = "Guided-planning contract fix: every cloud and local adapter now receives the actual outline or task JSON schema in its system instruction, including app/context enums, named HTTP checks and manual-check object fields. This works even when native JSON mode is off. Ollama input reservations account for both textual and native schemas. Approval, frozen acceptance, saved model settings, fallback and retry limits are unchanged. Adapter-wire and browser fixtures verify delivery, not live-model success or restored provider credit/quota. Retry the unapproved project using Plan in smaller steps after updating."
