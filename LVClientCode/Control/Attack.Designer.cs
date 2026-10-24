namespace LVClient.Control {
    partial class Attack {
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
            this.cboMyGeneral = new System.Windows.Forms.ComboBox();
            this.label1 = new System.Windows.Forms.Label();
            this.label2 = new System.Windows.Forms.Label();
            this.cboEnemyGeneral = new System.Windows.Forms.ComboBox();
            this.cboAttackMethod = new System.Windows.Forms.ComboBox();
            this.SuspendLayout();
            // 
            // cboMyGeneral
            // 
            this.cboMyGeneral.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.cboMyGeneral.FormattingEnabled = true;
            this.cboMyGeneral.Location = new System.Drawing.Point(3, 3);
            this.cboMyGeneral.Name = "cboMyGeneral";
            this.cboMyGeneral.Size = new System.Drawing.Size(97, 21);
            this.cboMyGeneral.TabIndex = 0;
            this.cboMyGeneral.SelectedIndexChanged += new System.EventHandler(this.cboMyGeneral_SelectedIndexChanged);
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(106, 11);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(18, 13);
            this.label1.TabIndex = 1;
            this.label1.Text = "vs";
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Location = new System.Drawing.Point(233, 11);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(31, 13);
            this.label2.TabIndex = 3;
            this.label2.Text = "bằng";
            // 
            // cboEnemyGeneral
            // 
            this.cboEnemyGeneral.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.cboEnemyGeneral.FormattingEnabled = true;
            this.cboEnemyGeneral.Location = new System.Drawing.Point(130, 3);
            this.cboEnemyGeneral.Name = "cboEnemyGeneral";
            this.cboEnemyGeneral.Size = new System.Drawing.Size(97, 21);
            this.cboEnemyGeneral.TabIndex = 4;
            this.cboEnemyGeneral.SelectedIndexChanged += new System.EventHandler(this.cboEnemyGeneral_SelectedIndexChanged);
            // 
            // cboAttackMethod
            // 
            this.cboAttackMethod.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.cboAttackMethod.Enabled = false;
            this.cboAttackMethod.FormattingEnabled = true;
            this.cboAttackMethod.Location = new System.Drawing.Point(270, 3);
            this.cboAttackMethod.Name = "cboAttackMethod";
            this.cboAttackMethod.Size = new System.Drawing.Size(69, 21);
            this.cboAttackMethod.TabIndex = 5;
            // 
            // Attack
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.cboAttackMethod);
            this.Controls.Add(this.cboEnemyGeneral);
            this.Controls.Add(this.label2);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.cboMyGeneral);
            this.Name = "Attack";
            this.Size = new System.Drawing.Size(372, 27);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Label label1;
        public System.Windows.Forms.ComboBox cboMyGeneral;
        private System.Windows.Forms.Label label2;
        public System.Windows.Forms.ComboBox cboEnemyGeneral;
        public System.Windows.Forms.ComboBox cboAttackMethod;
    }
}
