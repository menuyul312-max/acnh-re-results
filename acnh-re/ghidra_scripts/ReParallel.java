import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Parallel read-only pseudocode export from an already analyzed snapshot. */
public class ReParallel extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Path out = Paths.get(args[1]); Files.createDirectories(out);
        var queue = new ConcurrentLinkedQueue<Function>();
        for (String line : Files.readAllLines(Paths.get(args[0]))) {
            long va = Long.parseLong(line.trim(), 16);
            if (va < 0x1200000L || Files.exists(out.resolve(line.trim()+".c"))) continue;
            var address = currentProgram.getImageBase().add(va);
            Function f = currentProgram.getFunctionManager().getFunctionAt(address);
            var block = currentProgram.getMemory().getBlock(address);
            if (f != null && block != null && block.isExecute() && (va & 3) == 0) queue.add(f);
        }
        println("QUEUED " + queue.size());
        AtomicInteger ok = new AtomicInteger(), fail = new AtomicInteger();
        ExecutorService pool = Executors.newFixedThreadPool(3);
        List<Future<?>> jobs = new ArrayList<>();
        for (int worker=0;worker<3;worker++) jobs.add(pool.submit(() -> {
            DecompInterface di = new DecompInterface();
            di.openProgram(currentProgram);
            try {
                Function f;
                while ((f=queue.poll()) != null && !monitor.isCancelled()) {
                    long va=f.getEntryPoint().subtract(currentProgram.getImageBase());
                    String name=Long.toHexString(va)+".c";
                    if (Files.exists(out.resolve(name))) continue;
                    DecompileResults r=di.decompileFunction(f,25,monitor);
                    if (r!=null && r.getDecompiledFunction()!=null) {
                        Files.writeString(out.resolve(name),r.getDecompiledFunction().getC());
                        int count=ok.incrementAndGet();
                        if(count%500==0) println("PROGRESS ok="+count+" fail="+fail.get());
                    } else fail.incrementAndGet();
                }
            } catch(Exception e) { throw new RuntimeException(e); }
            finally { di.dispose(); }
        }));
        pool.shutdown();
        for(Future<?> job:jobs) job.get();
        println("COMPLETE ok="+ok.get()+" fail="+fail.get());
    }
}
