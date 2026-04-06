# Task 4 - Write all __init__.py files for the package structure
bash

cat > /mnt/user-data/outputs/__init__api_v1.py << 'EOF'
# backend/app/api/v1/__init__.py
# Makes the v1 routes directory a Python package.
# Import routers here so main.py can do: from app.api.v1 import auth, projects, twins
EOF

cat > /mnt/user-data/outputs/__init__api.py << 'EOF'
# backend/app/api/__init__.py
EOF

cat > /mnt/user-data/outputs/__init__models.py << 'EOF'
# backend/app/models/__init__.py
EOF

cat > /mnt/user-data/outputs/__init__core.py << 'EOF'
# backend/app/core/__init__.py
EOF

cat > /mnt/user-data/outputs/__init__sim_bridge.py << 'EOF'
# backend/app/sim_bridge/__init__.py
# Imports the domain enum so callers can do: from app.sim_bridge import SimDomain
from app.sim_bridge.base import (
    CudaXSolverBackend,
    SimDomain,
    SolverAdapter,
    get_adapter,
    register_adapter,
)

__all__ = [
    "SimDomain",
    "CudaXSolverBackend",
    "SolverAdapter",
    "register_adapter",
    "get_adapter",
]
EOF

cat > /mnt/user-data/outputs/__init__agents.py << 'EOF'
# backend/app/agents/__init__.py
EOF

cat > /mnt/user-data/outputs/__init__services.py << 'EOF'
# backend/app/services/__init__.py
EOF

cat > /mnt/user-data/outputs/__init__ai_physics.py << 'EOF'
# backend/app/ai_physics/__init__.py
# Phase 1+ — NIM client and DSR-CRAG pipeline
EOF

cat > /mnt/user-data/outputs/__init__app.py << 'EOF'
# backend/app/__init__.py
EOF

echo "All __init__.py files written."
##
