namespace LVClient.Command.CommonObj {
    partial class doitrai {
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

        #region Component Designer generated code

        /// <summary> 
        /// Required method for Designer support - do not modify 
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent() {
            this.chkOK = new System.Windows.Forms.CheckBox();
            this.X = new System.Windows.Forms.TextBox();
            this.Y = new System.Windows.Forms.TextBox();
            this.txtTen = new System.Windows.Forms.TextBox();
            this.SuspendLayout();
            // 
            // chkOK
            // 
            this.chkOK.AutoSize = true;
            this.chkOK.Location = new System.Drawing.Point(3, 7);
            this.chkOK.Name = "chkOK";
            this.chkOK.Size = new System.Drawing.Size(15, 14);
            this.chkOK.TabIndex = 1;
            this.chkOK.UseVisualStyleBackColor = true;
            // 
            // X
            // 
            this.X.Location = new System.Drawing.Point(199, 4);
            this.X.Name = "X";
            this.X.Size = new System.Drawing.Size(56, 20);
            this.X.TabIndex = 2;
            // 
            // Y
            // 
            this.Y.Location = new System.Drawing.Point(261, 4);
            this.Y.Name = "Y";
            this.Y.Size = new System.Drawing.Size(56, 20);
            this.Y.TabIndex = 3;
            // 
            // txtTen
            // 
            this.txtTen.BackColor = System.Drawing.SystemColors.ActiveCaptionText;
            this.txtTen.Location = new System.Drawing.Point(24, 4);
            this.txtTen.Name = "txtTen";
            this.txtTen.ReadOnly = true;
            this.txtTen.Size = new System.Drawing.Size(169, 20);
            this.txtTen.TabIndex = 4;
            // 
            // doitrai
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.txtTen);
            this.Controls.Add(this.Y);
            this.Controls.Add(this.X);
            this.Controls.Add(this.chkOK);
            this.Name = "doitrai";
            this.Size = new System.Drawing.Size(322, 28);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        public System.Windows.Forms.CheckBox chkOK;
        public System.Windows.Forms.TextBox Y;
        public System.Windows.Forms.TextBox txtTen;
        public System.Windows.Forms.TextBox X;
    }
}
