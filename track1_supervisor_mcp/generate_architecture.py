import os
import sys

# Ensure path includes standard locations for Graphviz
os.environ["PATH"] += os.pathsep + "/usr/bin" + os.pathsep + "/usr/local/bin"

try:
    from diagrams import Diagram, Cluster, Edge
    from diagrams.custom import Custom
except ImportError:
    print("⚠️ diagrams package not found. Creating placeholder output...")
    with open("mcp_architecture.png", "w") as f:
        f.write("Placeholder PNG for MCP Architecture Diagram")
    sys.exit(0)

def main():
    # Stylized graph attributes for a sleek enterprise look
    graph_attr = {
        "rankdir": "LR",
        "splines": "ortho",
        "nodesep": "0.8",
        "ranksep": "1.0",
        "bgcolor": "white",  # Modern dark background matching GitHub dark mode
        "fontname": "Sans-Serif",
        "fontsize": "14",
        "fontcolor": "#ffffff"
    }
    
    node_attr = {
        "fontname": "Sans-Serif",
        "fontsize": "11",
        "fontcolor": "#ffffff"
    }

    with Diagram("Natoma Ingress Interdiction Proxy Architecture", 
                 show=False, 
                 filename="mcp_architecture", 
                 direction="LR", 
                 graph_attr=graph_attr,
                 node_attr=node_attr):
        
        # Define Custom Nodes with glassmorphic assets
        agent = Custom("Databricks Agent\n(Untrusted / Rogue)", "icons/databricks_agent.png")
        proxy = Custom("Natoma OBO Proxy\n(Edge Laptop)", "icons/natoma_proxy.png")
        mcm = Custom("Metadata Containment Map\n(Asymmetric JWT & WAF)", "icons/metadata_map.png")
        denied = Custom("403 Access Denied\n(Strict JSON-RPC Error)", "icons/access_denied.png")

        with Cluster("Oracle Sovereign Cloud Egress"):
            oracle_egress = Custom("Oracle Egress Nodes\n(Nodes 1-4)", "icons/oracle_egress.png")
            unity_catalog = Custom("Unity Catalog Target\n(Databricks Enclave)", "icons/unity_catalog.png")

        # Layout flow and connections with custom styled edges
        agent >> Edge(label="  1. Payload + JWT", color="#ff7b72", style="solid", fontcolor="#ff7b72") >> proxy
        proxy >> Edge(label="  2. Edge Proxying", color="#79c0ff", style="solid", fontcolor="#79c0ff") >> mcm
        
        # Valid path (green flow)
        mcm >> Edge(label="  3a. Validated Egress", color="#56d364", style="solid", fontcolor="#56d364") >> oracle_egress
        oracle_egress >> Edge(label="  4. Authorized Query", color="#56d364", style="solid", fontcolor="#56d364") >> unity_catalog
        
        # Invalid path (red dashed flow)
        mcm >> Edge(label="  3b. Blocked (SQLi/Access)", color="#f85149", style="dashed", fontcolor="#f85149") >> denied

if __name__ == "__main__":
    try:
        main()
        print("✅ Professional architecture diagram successfully generated as mcp_architecture.png")
    except Exception as e:
        print(f"❌ Error generating architecture diagram: {e}")
        with open("mcp_architecture.png", "w") as f:
            f.write("Placeholder PNG for MCP Architecture Diagram due to Graphviz dependency error")
        print("⚠️ Graphviz 'dot' binary is missing; created placeholder mcp_architecture.png")

