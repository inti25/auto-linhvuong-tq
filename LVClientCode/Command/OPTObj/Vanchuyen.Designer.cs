namespace LVClient.Command.OPTObj {
    partial class Vanchuyen {
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
            this.cboSource = new System.Windows.Forms.ComboBox();
            this.cboDesc = new System.Windows.Forms.ComboBox();
            this.txtMONEY = new System.Windows.Forms.TextBox();
            this.txtFOOD = new System.Windows.Forms.TextBox();
            this.txtIRON = new System.Windows.Forms.TextBox();
            this.txtWOOD = new System.Windows.Forms.TextBox();
            this.txtSTONE = new System.Windows.Forms.TextBox();
            this.chkOK = new System.Windows.Forms.CheckBox();
            this.SuspendLayout();
            // 
            // cboSource
            // 
            this.cboSource.FormattingEnabled = true;
            this.cboSource.Location = new System.Drawing.Point(24, 3);
            this.cboSource.Name = "cboSource";
            this.cboSource.Size = new System.Drawing.Size(92, 21);
            this.cboSource.TabIndex = 0;
            // 
            // cboDesc
            // 
            this.cboDesc.FormattingEnabled = true;
            this.cboDesc.Location = new System.Drawing.Point(122, 4);
            this.cboDesc.Name = "cboDesc";
            this.cboDesc.Size = new System.Drawing.Size(105, 21);
            this.cboDesc.TabIndex = 0;
            // 
            // txtMONEY
            // 
            this.txtMONEY.Location = new System.Drawing.Point(233, 4);
            this.txtMONEY.Name = "txtMONEY";
            this.txtMONEY.Size = new System.Drawing.Size(52, 20);
            this.txtMONEY.TabIndex = 1;
            // 
            // txtFOOD
            // 
            this.txtFOOD.Location = new System.Drawing.Point(291, 4);
            this.txtFOOD.Name = "txtFOOD";
            this.txtFOOD.Size = new System.Drawing.Size(52, 20);
            this.txtFOOD.TabIndex = 2;
            // 
            // txtIRON
            // 
            this.txtIRON.Location = new System.Drawing.Point(407, 4);
            this.txtIRON.Name = "txtIRON";
            this.txtIRON.Size = new System.Drawing.Size(52, 20);
            this.txtIRON.TabIndex = 3;
            // 
            // txtWOOD
            // 
            this.txtWOOD.Location = new System.Drawing.Point(349, 4);
            this.txtWOOD.Name = "txtWOOD";
            this.txtWOOD.Size = new System.Drawing.Size(52, 20);
            this.txtWOOD.TabIndex = 4;
            // 
            // txtSTONE
            // 
            this.txtSTONE.Location = new System.Drawing.Point(465, 5);
            this.txtSTONE.Name = "txtSTONE";
            this.txtSTONE.Size = new System.Drawing.Size(52, 20);
            this.txtSTONE.TabIndex = 5;
            // 
            // chkOK
            // 
            this.chkOK.AutoSize = true;
            this.chkOK.Location = new System.Drawing.Point(3, 7);
            this.chkOK.Name = "chkOK";
            this.chkOK.Size = new System.Drawing.Size(15, 14);
            this.chkOK.TabIndex = 6;
            this.chkOK.UseVisualStyleBackColor = true;
            // 
            // Vanchuyen
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.chkOK);
            this.Controls.Add(this.txtSTONE);
            this.Controls.Add(this.txtWOOD);
            this.Controls.Add(this.txtIRON);
            this.Controls.Add(this.txtFOOD);
            this.Controls.Add(this.txtMONEY);
            this.Controls.Add(this.cboDesc);
            this.Controls.Add(this.cboSource);
            this.Name = "Vanchuyen";
            this.Size = new System.Drawing.Size(523, 30);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        public System.Windows.Forms.ComboBox cboSource;
        public System.Windows.Forms.TextBox txtMONEY;
        public System.Windows.Forms.TextBox txtFOOD;
        public System.Windows.Forms.TextBox txtIRON;
        public System.Windows.Forms.TextBox txtWOOD;
        public System.Windows.Forms.TextBox txtSTONE;
        public System.Windows.Forms.ComboBox cboDesc;
        public System.Windows.Forms.CheckBox chkOK;

    }
}
