import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.nio.file.*;
import java.io.*;

public class ReInventory extends GhidraScript {
    public void run() throws Exception {
        var base = currentProgram.getImageBase();
        try (BufferedWriter out = Files.newBufferedWriter(Paths.get(getScriptArgs()[0]))) {
            out.write("elf_va\tbody_bytes\tend_va\tname\treturn_type\n");
            int count=0;
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                monitor.checkCancelled();
                var a=f.getEntryPoint();
                var block=currentProgram.getMemory().getBlock(a);
                if(block==null || !block.isExecute() || (a.getOffset()&3)!=0) continue;
                out.write(Long.toHexString(a.subtract(base))+"\t"+f.getBody().getNumAddresses()+"\t"+
                    Long.toHexString(f.getBody().getMaxAddress().subtract(base))+"\t"+
                    f.getName()+"\t"+f.getReturnType().getName()+"\n");
                count++;
            }
            println("INVENTORY " + count);
        }
    }
}
