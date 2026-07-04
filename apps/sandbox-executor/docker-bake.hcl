variable "CI" {
  default = "false"
}

target "common" {
  context = "apps/sandbox-executor"
  dockerfile = "Dockerfile"
  cache-from = CI == "true" ? ["type=gha,scope=holon-sandbox-executor"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=holon-sandbox-executor"] : []
}

target "base" {
  inherits = ["common"]
  target = "holon-base"
  tags = ["holon/base"]
}

target "agent-claude" {
  inherits = ["common"]
  target = "agent-claude"
  tags = ["holon/agent-claude"]
  contexts = {
    holon-base = "target:base"
  }
}

target "agent-codex" {
  inherits = ["common"]
  target = "agent-codex"
  tags = ["holon/agent-codex"]
  contexts = {
    holon-base = "target:base"
  }
}

target "agent-gemini" {
  inherits = ["common"]
  target = "agent-gemini"
  tags = ["holon/agent-gemini"]
  contexts = {
    holon-base = "target:base"
  }
}

target "agent-opencode" {
  inherits = ["common"]
  target = "agent-opencode"
  tags = ["holon/agent-opencode"]
  contexts = {
    holon-base = "target:base"
  }
}

target "agent-open-codex" {
  inherits = ["common"]
  target = "agent-open-codex"
  tags = ["holon/agent-open-codex"]
  contexts = {
    holon-base = "target:base"
  }
}

target "agent-pi" {
  inherits = ["common"]
  target = "agent-pi"
  tags = ["holon/agent-pi"]
  contexts = {
    holon-base = "target:base"
  }
}

target "agent-antigravity" {
  inherits = ["common"]
  target = "agent-antigravity"
  tags = ["holon/agent-antigravity"]
  contexts = {
    holon-base = "target:base"
  }
}

target "orchestrator" {
  inherits = ["common"]
  target = "holon-orchestrator"
  tags = ["holon/orchestrator"]
  contexts = {
    holon-base = "target:base"
  }
}

group "default" {
  targets = [
    "base",
    "agent-claude",
    "agent-codex",
    "agent-gemini",
    "agent-opencode",
    "agent-open-codex",
    "agent-pi",
    "agent-antigravity",
    "orchestrator"
  ]
}
