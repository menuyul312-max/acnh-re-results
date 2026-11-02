import ghidra.app.script.GhidraScript;

public class ReOptions extends GhidraScript {
    public void run() throws Exception {
        for (String option : new String[]{"Decompiler Parameter ID", "Aggressive Instruction Finder",
                "Condense Filler Bytes", "Variadic Function Signature Override"}) {
            try { setAnalysisOption(currentProgram, option, "false"); }
            catch (Exception e) { println("Option unavailable: " + option); }
        }
    }
}
