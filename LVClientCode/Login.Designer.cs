namespace LVClient {
    partial class Login {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing) {
            if (disposing && (components != null)) {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent() {
            this.components = new System.ComponentModel.Container();
            this.label54 = new System.Windows.Forms.Label();
            this.label55 = new System.Windows.Forms.Label();
            this.label56 = new System.Windows.Forms.Label();
            this.cboServer = new System.Windows.Forms.ComboBox();
            this.cmdLogin = new System.Windows.Forms.Button();
            this.txtLvPassword = new System.Windows.Forms.TextBox();
            this.txtUsername = new System.Windows.Forms.TextBox();
            this.wbLogin = new System.Windows.Forms.WebBrowser();
            this.timer1 = new System.Windows.Forms.Timer(this.components);
            this.SuspendLayout();
            // 
            // label54
            // 
            this.label54.AutoSize = true;
            this.label54.Location = new System.Drawing.Point(0, 72);
            this.label54.Name = "label54";
            this.label54.Size = new System.Drawing.Size(38, 13);
            this.label54.TabIndex = 35;
            this.label54.Text = "Server";
            // 
            // label55
            // 
            this.label55.AutoSize = true;
            this.label55.Location = new System.Drawing.Point(0, 45);
            this.label55.Name = "label55";
            this.label55.Size = new System.Drawing.Size(53, 13);
            this.label55.TabIndex = 36;
            this.label55.Text = "Password";
            // 
            // label56
            // 
            this.label56.AutoSize = true;
            this.label56.Location = new System.Drawing.Point(0, 19);
            this.label56.Name = "label56";
            this.label56.Size = new System.Drawing.Size(55, 13);
            this.label56.TabIndex = 37;
            this.label56.Text = "Username";
            // 
            // cboServer
            // 
            this.cboServer.FormattingEnabled = true;
            this.cboServer.Items.AddRange(new object[] {
            "1. Quan độ",
            "2. Trường bản",
            "3. Phàn thành",
            "4. Di lăng",
            "5. Nhai đình"});
            this.cboServer.Location = new System.Drawing.Point(61, 64);
            this.cboServer.Name = "cboServer";
            this.cboServer.Size = new System.Drawing.Size(157, 21);
            this.cboServer.TabIndex = 33;
            this.cboServer.Text = "1. Quan độ";
            this.cboServer.SelectedIndexChanged += new System.EventHandler(this.cboServer_SelectedIndexChanged);
            // 
            // cmdLogin
            // 
            this.cmdLogin.Location = new System.Drawing.Point(61, 91);
            this.cmdLogin.Name = "cmdLogin";
            this.cmdLogin.Size = new System.Drawing.Size(63, 28);
            this.cmdLogin.TabIndex = 34;
            this.cmdLogin.Text = "Login";
            this.cmdLogin.UseVisualStyleBackColor = true;
            this.cmdLogin.Click += new System.EventHandler(this.cmdLogin_Click);
            // 
            // txtLvPassword
            // 
            this.txtLvPassword.Location = new System.Drawing.Point(61, 38);
            this.txtLvPassword.Name = "txtLvPassword";
            this.txtLvPassword.PasswordChar = '*';
            this.txtLvPassword.Size = new System.Drawing.Size(88, 20);
            this.txtLvPassword.TabIndex = 32;
            // 
            // txtUsername
            // 
            this.txtUsername.Location = new System.Drawing.Point(61, 12);
            this.txtUsername.Name = "txtUsername";
            this.txtUsername.Size = new System.Drawing.Size(88, 20);
            this.txtUsername.TabIndex = 31;
            // 
            // wbLogin
            // 
            this.wbLogin.AllowWebBrowserDrop = false;
            this.wbLogin.Location = new System.Drawing.Point(296, 138);
            this.wbLogin.MinimumSize = new System.Drawing.Size(20, 20);
            this.wbLogin.Name = "wbLogin";
            this.wbLogin.ScriptErrorsSuppressed = true;
            this.wbLogin.Size = new System.Drawing.Size(189, 160);
            this.wbLogin.TabIndex = 38;
            this.wbLogin.DocumentCompleted += new System.Windows.Forms.WebBrowserDocumentCompletedEventHandler(this.wbLogin_DocumentCompleted);
            // 
            // timer1
            // 
            this.timer1.Tick += new System.EventHandler(this.timer1_Tick);
            // 
            // Login
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(700, 340);
            this.Controls.Add(this.label54);
            this.Controls.Add(this.label55);
            this.Controls.Add(this.label56);
            this.Controls.Add(this.cboServer);
            this.Controls.Add(this.cmdLogin);
            this.Controls.Add(this.txtLvPassword);
            this.Controls.Add(this.txtUsername);
            this.Controls.Add(this.wbLogin);
            this.Name = "Login";
            this.Text = "Login";
            this.Load += new System.EventHandler(this.Login_Load);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Label label54;
        private System.Windows.Forms.Label label55;
        private System.Windows.Forms.Label label56;
        private System.Windows.Forms.ComboBox cboServer;
        private System.Windows.Forms.Button cmdLogin;
        private System.Windows.Forms.TextBox txtLvPassword;
        private System.Windows.Forms.TextBox txtUsername;
        private System.Windows.Forms.WebBrowser wbLogin;
        private System.Windows.Forms.Timer timer1;
    }
}