import json
import os
import statistics

# Configuration
INPUT_DIR = "./analysis_in"
OUTPUT_DIR = "./analysis_out"

def ensure_dirs():
    if not os.path.exists(INPUT_DIR):
        os.makedirs(INPUT_DIR)
        print(f"Created input directory: {INPUT_DIR}. Please place JSON logs there.")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def get_safe(data, path, default="N/A"):
    """Helper to safely get nested dictionary values."""
    try:
        for key in path:
            data = data[key]
        return data
    except (KeyError, TypeError, IndexError):
        return default

def calculate_stats(phase_messages):
    """Iterates through messages to calculate token and latency statistics."""
    stats = {
        "llm_calls": 0,
        "input_tokens": [],
        "output_tokens": [],
        "latency_ms": []
    }

    for phase in phase_messages:
        for agent_msg in phase.get("agent_messages", []):
            if not agent_msg.get("action_messages"):
                continue
            
            for action in agent_msg["action_messages"]:
                # specific to the model generation step
                if action.get("resource_id") == "model" and "additional_metadata" in action:
                    meta = action["additional_metadata"]
                    stats["llm_calls"] += 1
                    stats["input_tokens"].append(meta.get("input_tokens", 0))
                    stats["output_tokens"].append(meta.get("output_tokens", 0))
                    stats["latency_ms"].append(meta.get("time_taken_in_ms", 0))

    return stats

def write_header(f, title):
    f.write(f"\n{'='*60}\n")
    f.write(f" {title.upper()}\n")
    f.write(f"{'='*60}\n")

def process_log_file(filename):
    input_path = os.path.join(INPUT_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, filename.replace(".json", ".txt"))

    try:
        with open(input_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return

    with open(output_path, 'w', encoding='utf-8') as f:
        # 1. Workflow Metadata
        write_header(f, "Workflow Metadata")
        wf_meta = data.get("workflow_metadata", {})
        task = wf_meta.get("task", {})
        summary = wf_meta.get("workflow_summary", {})
        
        f.write(f"Workflow Name:   {wf_meta.get('workflow_name', 'N/A')}\n")
        f.write(f"Task Directory:  {task.get('task_dir', 'N/A')}\n")
        f.write(f"Bounty Number:   {task.get('bounty_number', 'N/A')}\n")
        f.write(f"Status:          {'COMPLETE' if summary.get('complete') else 'INCOMPLETE'}\n")
        f.write(f"Success:         {'YES' if summary.get('success') else 'NO'}\n")
        
        # Bounty Specifics
        bounty_meta = get_safe(data, ["additional_metadata", "bounty_metadata"], {})
        if bounty_meta != "N/A":
            f.write(f"-" * 30 + "\n")
            f.write(f"CVE:             {bounty_meta.get('CVE', 'N/A')}\n")
            f.write(f"Payout:          ${bounty_meta.get('disclosure_bounty', '0')}\n")

        # 2. Resources & Statistics
        write_header(f, "Model & Resource Statistics")
        
        # Model Config
        model_config = get_safe(data, ["resources_used", "model", "config"], {})
        f.write(f"Model Name:          {model_config.get('model', 'Unknown')}\n")
        f.write(f"Temperature:         {model_config.get('temperature', 'N/A')}\n")
        f.write(f"Max Input Tokens:    {model_config.get('max_input_tokens', 'N/A')}\n")
        f.write(f"Max Output Tokens:   {model_config.get('max_output_tokens', 'N/A')}\n")
        
        # Usage Stats
        stats = calculate_stats(data.get("phase_messages", []))
        
        if stats["llm_calls"] > 0:
            avg_in = statistics.mean(stats["input_tokens"])
            avg_out = statistics.mean(stats["output_tokens"])
            
            total_lat = sum(stats["latency_ms"])
            avg_lat = statistics.mean(stats["latency_ms"])
            
            f.write(f"\nTotal LLM Calls:     {stats['llm_calls']}\n")
            f.write(f"Total Tokens:        In: {sum(stats['input_tokens']):,} | Out: {sum(stats['output_tokens']):,}\n")
            f.write(f"Avg Tokens:          In: {avg_in:.2f} | Out: {avg_out:.2f}\n")
            f.write(f"Latency (ms):        Total: {total_lat:,.2f} | Avg: {avg_lat:,.2f}\n")
        else:
            f.write("\nNo LLM calls detected in phase messages.\n")

        # 3. Play-by-Play
        write_header(f, "Conversation Play-by-Play")
        
        phases = data.get("phase_messages", [])
        for p_idx, phase in enumerate(phases):
            f.write(f"\n### PHASE {p_idx}: {phase.get('phase_id', 'Unknown')}\n")
            
            agent_msgs = phase.get("agent_messages", [])
            for msg in agent_msgs:
                agent_id = msg.get("agent_id")
                
                # Handle System/User prompts (NO TRUNCATION)
                if agent_id == "system" or agent_id == "user":
                    f.write(f"\n[{agent_id.upper()} MESSAGE]\n")
                    f.write(f"{msg.get('message', '').strip()}\n")
                    continue

                # Handle Executor/Model interactions
                action_msgs = msg.get("action_messages", [])
                if not action_msgs:
                    continue

                for action in action_msgs:
                    res_id = action.get("resource_id", "")
                    
                    # Case A: The Model Thinking and Commanding
                    if res_id == "model":
                        f.write(f"\n{'-'*20} MODEL THOUGHT & COMMAND {'-'*20}\n")
                        raw_msg = action.get("message", "")
                        cmd = action.get("command", "")
                        
                        if "Thought:" in raw_msg:
                            f.write(raw_msg.strip() + "\n")
                        else:
                            f.write(f"Content: {raw_msg}\n")
                            
                        if cmd:
                            f.write(f"\n>>> COMMAND: {cmd}\n")

                    # Case B: The Tool/Environment Responding
                    elif "kali" in res_id or "env" in res_id:
                        f.write(f"\n{'.'*20} SYSTEM OBSERVATION {'.'*20}\n")
                        output = action.get("message", "").strip()
                        if not output:
                            output = "[No Output]"
                        f.write(f"{output}\n")
                    
                    # Case C: Submit Agent
                    elif agent_id == "detect_agent":
                        f.write(f"\n!!! DETECT AGENT: {action.get('message')}\n")

    print(f"Processed: {filename} -> {output_path}")

def main():
    ensure_dirs()
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".json")]
    
    if not files:
        print(f"No JSON files found in {INPUT_DIR}")
        return

    print(f"Found {len(files)} log files. Processing...")
    for filename in files:
        process_log_file(filename)
    print("Done.")

if __name__ == "__main__":
    main()