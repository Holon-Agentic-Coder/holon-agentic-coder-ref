variable "CI" {
  default = "false"
}

target "common" {
  context = "apps/sandbox-executor"
  dockerfile = "Dockerfile"
}

target "base" {
  inherits = ["common"]
  target = "holon-base"
  tags = ["holon/base"]
  cache-from = CI == "true" ? ["type=gha,scope=base"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=base"] : []
}

target "agent-claude" {
  inherits = ["common"]
  target = "agent-claude"
  tags = ["holon/agent-claude"]
  contexts = {
    holon-base = "target:base"
  }
  cache-from = CI == "true" ? ["type=gha,scope=agent-claude"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=agent-claude"] : []
}

target "agent-codex" {
  inherits = ["common"]
  target = "agent-codex"
  tags = ["holon/agent-codex"]
  contexts = {
    holon-base = "target:base"
  }
  cache-from = CI == "true" ? ["type=gha,scope=agent-codex"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=agent-codex"] : []
}

target "agent-gemini" {
  inherits = ["common"]
  target = "agent-gemini"
  tags = ["holon/agent-gemini"]
  contexts = {
    holon-base = "target:base"
  }
  cache-from = CI == "true" ? ["type=gha,scope=agent-gemini"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=agent-gemini"] : []
}

target "agent-opencode" {
  inherits = ["common"]
  target = "agent-opencode"
  tags = ["holon/agent-opencode"]
  contexts = {
    holon-base = "target:base"
  }
  cache-from = CI == "true" ? ["type=gha,scope=agent-opencode"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=agent-opencode"] : []
}

target "agent-open-codex" {
  inherits = ["common"]
  target = "agent-open-codex"
  tags = ["holon/agent-open-codex"]
  contexts = {
    holon-base = "target:base"
  }
  cache-from = CI == "true" ? ["type=gha,scope=agent-open-codex"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=agent-open-codex"] : []
}

target "agent-pi" {
  inherits = ["common"]
  target = "agent-pi"
  tags = ["holon/agent-pi"]
  contexts = {
    holon-base = "target:base"
  }
  cache-from = CI == "true" ? ["type=gha,scope=agent-pi"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=agent-pi"] : []
}

target "agent-antigravity" {
  inherits = ["common"]
  target = "agent-antigravity"
  tags = ["holon/agent-antigravity"]
  contexts = {
    holon-base = "target:base"
  }
  cache-from = CI == "true" ? ["type=gha,scope=agent-antigravity"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=agent-antigravity"] : []
}

target "orchestrator" {
  inherits = ["common"]
  target = "holon-orchestrator"
  tags = ["holon/orchestrator"]
  contexts = {
    holon-base = "target:base"
  }
  cache-from = CI == "true" ? ["type=gha,scope=orchestrator"] : []
  cache-to = CI == "true" ? ["type=gha,mode=max,scope=orchestrator"] : []
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
