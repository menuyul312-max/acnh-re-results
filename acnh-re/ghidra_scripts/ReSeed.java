import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import java.io.*;
import java.nio.file.*;

public class ReSeed extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Address base = currentProgram.getImageBase();
        println("ELF image base=" + base);
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        File out = new File(args[1]); out.mkdirs();
        int ok = 0, fail = 0;
        for (String line : Files.readAllLines(Paths.get(args[0]))) {
            monitor.checkCancelled();
            String va = line.trim();
            if (va.isEmpty() || va.startsWith("#")) continue;
            File target = new File(out, va + ".c");
            if (target.exists()) continue;
            Address a = base.add(Long.parseLong(va, 16));
            var block = currentProgram.getMemory().getBlock(a);
            if (block == null || !block.isExecute() || (a.getOffset() & 3) != 0) {
                println("SKIP_NONCODE " + va); fail++; continue;
            }
            disassemble(a);
            Function f = currentProgram.getFunctionManager().getFunctionAt(a);
            if (f == null) {
                new CreateFunctionCmd(a).applyTo(currentProgram);
                f = currentProgram.getFunctionManager().getFunctionAt(a);
            }
            if (f == null) { println("NO_FUNCTION " + va); fail++; continue; }
            DecompileResults result = di.decompileFunction(f, 25, monitor);
            if (result != null && result.getDecompiledFunction() != null) {
                Files.writeString(target.toPath(), result.getDecompiledFunction().getC());
                ok++;
            } else { println("FAIL " + va); fail++; }
            if ((ok + fail) % 25 == 0) println("PROGRESS ok="+ok+" fail="+fail+" va="+va);
        }
        di.dispose();
        println("COMPLETE ok=" + ok + " fail=" + fail);
    }
}
