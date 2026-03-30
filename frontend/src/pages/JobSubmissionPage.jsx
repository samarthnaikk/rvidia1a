import { useState } from "react";
import { createJob, registerHost } from "../lib/api";

function JobSubmissionPage({ authToken, onBackDashboard, onJobCreated }) {
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [command, setCommand] = useState("python main.py");
  const [hostNodeId, setHostNodeId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const handleSubmit = async () => {
    if (!repoUrl.trim()) {
      setErrorMessage("Please enter a repository URL before creating a job.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const job = await createJob(authToken, {
        repo_url: repoUrl.trim(),
        branch: branch.trim() || "main",
        command: command.trim(),
      });

      if (hostNodeId.trim()) {
        await registerHost(authToken, job.id, hostNodeId.trim());
      }

      setSuccessMessage(`Job created: ${job.id}`);
      onJobCreated(job.id);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="relative min-h-screen w-full overflow-hidden bg-[#020711] px-6 pb-12 pt-10 text-slate-100 md:px-10 lg:px-14">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_78%_24%,rgba(110,255,181,0.15),transparent_34%),linear-gradient(120deg,rgba(6,14,24,0.94)_0%,rgba(3,8,17,0.96)_46%,rgba(2,7,14,0.98)_100%)]" />

      <div className="relative z-10 mx-auto w-full max-w-[900px]">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="font-space text-[42px] font-bold uppercase tracking-[3px] text-slate-100 md:text-[48px]">
            Submit GPU Job
          </h1>
          <button
            className="font-jetbrains h-[40px] border border-white/30 px-5 text-[12px] uppercase tracking-[2px] text-slate-300 transition hover:border-white/60 hover:text-white"
            onClick={onBackDashboard}
            type="button"
          >
            ← Back
          </button>
        </div>

        <div className="rounded-[10px] border border-white/15 bg-[#090f1ccc] p-7 shadow-[0_0_0_1px_rgba(148,163,184,0.08),0_24px_60px_rgba(2,6,23,0.5)] backdrop-blur-sm md:p-8">
          <div className="mb-7">
            <label className="font-jetbrains mb-2 block text-[12px] uppercase tracking-[3px] text-slate-400">
              Repository URL
            </label>
            <input
              className="font-jetbrains h-[50px] w-full border-b border-b-white/15 bg-[#090f1ccc] px-0 text-[16px] text-slate-200 outline-none placeholder:text-slate-500/75 focus:border-b-emerald-300/60"
              onChange={(event) => setRepoUrl(event.target.value)}
              placeholder="https://github.com/rvidia/core-repo.git"
              type="text"
              value={repoUrl}
            />
          </div>

          <div className="mb-7 grid gap-7 md:grid-cols-2">
            <div>
              <label className="font-jetbrains mb-2 block text-[12px] uppercase tracking-[3px] text-slate-400">
                Branch
              </label>
              <input
                className="font-jetbrains h-[50px] w-full border-b border-b-white/15 bg-[#090f1ccc] px-0 text-[16px] text-slate-200 outline-none placeholder:text-slate-500/75 focus:border-b-emerald-300/60"
                onChange={(event) => setBranch(event.target.value)}
                placeholder="main"
                type="text"
                value={branch}
              />
            </div>

            <div>
              <label className="font-jetbrains mb-2 block text-[12px] uppercase tracking-[3px] text-slate-400">
                Host Node ID <span className="text-slate-500">(Optional)</span>
              </label>
              <input
                className="font-jetbrains h-[50px] w-full border-b border-b-white/15 bg-[#090f1ccc] px-0 text-[16px] text-slate-200 outline-none placeholder:text-slate-500/75 focus:border-b-emerald-300/60"
                onChange={(event) => setHostNodeId(event.target.value)}
                placeholder="NODE_X_042"
                type="text"
                value={hostNodeId}
              />
            </div>
          </div>

          <div className="mb-8">
            <label className="font-jetbrains mb-2 block text-[12px] uppercase tracking-[3px] text-slate-400">
              Execution Command
            </label>
            <input
              className="font-jetbrains h-[50px] w-full border-b border-b-white/15 bg-[#090f1ccc] px-0 text-[16px] text-slate-200 outline-none placeholder:text-slate-500/75 focus:border-b-emerald-300/60"
              onChange={(event) => setCommand(event.target.value)}
              placeholder="python mainfile.py"
              type="text"
              value={command}
            />
          </div>

          <div className="mb-8 border border-white/10 bg-[#0f1624bd] px-4 py-3.5">
            <p className="font-jetbrains text-[12px] leading-[1.65] tracking-[0.3px] text-slate-400">
              <span className="mr-2 text-emerald-300">ⓘ</span>
              Jobs are scheduled across available H100 clusters. Estimated spin-up time is <span className="text-emerald-300">~14s</span>.
              Ensure your repository contains a valid <span className="text-slate-300">requirements.txt</span> or <span className="text-slate-300">environment.yml</span> for automated provisioning.
            </p>
          </div>

          {errorMessage && (
            <p className="font-jetbrains mb-4 text-[13px] text-red-300">{errorMessage}</p>
          )}
          {successMessage && (
            <p className="font-jetbrains mb-4 text-[13px] text-emerald-300">{successMessage}</p>
          )}

          <button
            className="font-jetbrains h-[54px] w-full border border-emerald-200/70 bg-[#95f2bd] text-[15px] font-bold uppercase tracking-[3px] text-[#0b2d1e] shadow-[0_0_22px_rgba(134,239,172,0.22)] transition hover:brightness-105"
            disabled={isSubmitting}
            onClick={handleSubmit}
            type="button"
          >
            {isSubmitting ? "Submitting..." : "Create Job"}
          </button>

          <p className="font-jetbrains mt-5 text-center text-[10px] uppercase tracking-[3px] text-slate-500">
            Finalizing environment configuration: v_4.2.1-stable
          </p>
        </div>
      </div>
    </section>
  );
}

export default JobSubmissionPage;
